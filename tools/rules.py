"""Domain rules and referential integrity.

These encode what the source material learned the hard way. The comparison
tolerance exists because capacitance is written as a float in YAML.
"""

from __future__ import annotations

import math

from tools.issues import ERROR, WARNING, Issue
from tools.model import Board, Dataset

CAPACITANCE_TOLERANCE = 1e-2


def _same_capacitance(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=CAPACITANCE_TOLERANCE)


def _board_location(board: Board) -> str:
    if board.path is not None:
        return board.path.as_posix()
    return board.id


def _check_board(board: Board, dataset: Dataset) -> list[Issue]:
    issues: list[Issue] = []
    location = _board_location(board)

    if not board.sources:
        verified_capacitor = next(
            (
                capacitor
                for capacitor in board.capacitors
                if capacitor.effective_verification(board.verification) == "verified"
            ),
            None,
        )
        if board.verification == "verified":
            issues.append(
                Issue(
                    ERROR,
                    "verified-without-source",
                    location,
                    "verification is 'verified' but the board has no sources",
                )
            )
        elif verified_capacitor is not None:
            index = board.capacitors.index(verified_capacitor)
            issues.append(
                Issue(
                    ERROR,
                    "verified-without-source",
                    f"{location}:capacitors/{index}",
                    "verification is 'verified' but the board has no sources",
                )
            )

    if not board.sources:
        issues.append(
            Issue(WARNING, "no-sources", location, "the board cites no sources")
        )

    machine = dataset.machines.get(board.machine)
    if machine is None:
        issues.append(
            Issue(
                ERROR,
                "unknown-machine",
                location,
                f"machine {board.machine!r} is not defined",
            )
        )
    elif board.board not in machine.board_order:
        issues.append(
            Issue(
                ERROR,
                "board-kind-not-ordered",
                location,
                f"board kind {board.board!r} is missing from the board_order of "
                f"machine {machine.id!r}",
            )
        )

    if board.path is not None:
        expected_id = f"{board.machine}-{board.path.stem}"
        if board.id != expected_id:
            issues.append(
                Issue(
                    ERROR,
                    "id-path-mismatch",
                    location,
                    f"id is {board.id!r} but the path implies {expected_id!r}",
                )
            )
        parent = board.path.parent.name
        if parent and parent != board.machine:
            issues.append(
                Issue(
                    ERROR,
                    "id-path-mismatch",
                    location,
                    f"the board sits in {parent!r} but names machine "
                    f"{board.machine!r}",
                )
            )

    for index, capacitor in enumerate(board.capacitors):
        where = f"{location}:capacitors/{index}"

        if (
            capacitor.original_voltage_v is not None
            and capacitor.voltage_v < capacitor.original_voltage_v
        ):
            issues.append(
                Issue(
                    ERROR,
                    "voltage-downgrade",
                    where,
                    f"{capacitor.voltage_v} V is below the original "
                    f"{capacitor.original_voltage_v} V; voltage is only revised "
                    f"upward",
                )
            )

        if not capacitor.designators:
            issues.append(
                Issue(
                    WARNING,
                    "no-designators",
                    where,
                    "the position has no reference designators",
                )
            )

        if capacitor.series is not None and capacitor.series not in dataset.series:
            issues.append(
                Issue(
                    ERROR,
                    "unknown-series",
                    where,
                    f"series {capacitor.series!r} is not defined",
                )
            )

        if capacitor.part is None:
            continue

        part = dataset.parts.get(capacitor.part)
        if part is None:
            issues.append(
                Issue(
                    ERROR,
                    "unknown-part",
                    where,
                    f"part {capacitor.part!r} is not defined",
                )
            )
            continue

        if part.type != capacitor.type:
            issues.append(
                Issue(
                    ERROR,
                    "part-mismatch",
                    where,
                    f"pinned part {part.id!r} is {part.type}, the position is "
                    f"{capacitor.type}",
                )
            )
        if not _same_capacitance(part.capacitance_uf, capacitor.capacitance_uf):
            issues.append(
                Issue(
                    ERROR,
                    "part-mismatch",
                    where,
                    f"pinned part {part.id!r} is {part.capacitance_uf} uF, the "
                    f"position needs {capacitor.capacitance_uf} uF",
                )
            )
        if part.voltage_v < capacitor.voltage_v:
            issues.append(
                Issue(
                    ERROR,
                    "part-mismatch",
                    where,
                    f"pinned part {part.id!r} is rated {part.voltage_v} V, below "
                    f"the position's {capacitor.voltage_v} V",
                )
            )

    return issues


def _check_reference(dataset: Dataset) -> list[Issue]:
    issues: list[Issue] = []

    for part in dataset.parts.values():
        if part.series not in dataset.series:
            issues.append(
                Issue(
                    ERROR,
                    "unknown-series",
                    f"reference/parts.yaml:{part.id}",
                    f"series {part.series!r} is not defined",
                )
            )

    offered = {
        part_id for entries in dataset.offers.values() for part_id in entries
    }
    for supplier_id, entries in dataset.offers.items():
        location = f"reference/offers/{supplier_id}.yaml"
        if supplier_id not in dataset.suppliers:
            issues.append(
                Issue(
                    ERROR,
                    "unknown-offer-supplier",
                    location,
                    f"no supplier is defined with id {supplier_id!r}",
                )
            )
        for part_id in entries:
            if part_id not in dataset.parts:
                issues.append(
                    Issue(
                        ERROR,
                        "unknown-offer-part",
                        f"{location}:{part_id}",
                        f"part {part_id!r} is not defined",
                    )
                )

    for part_id in dataset.parts:
        if part_id not in offered:
            issues.append(
                Issue(
                    WARNING,
                    "part-without-offer",
                    f"reference/parts.yaml:{part_id}",
                    "no supplier lists a stock number for this part",
                )
            )

    for machine_id in dataset.machines:
        if not any(board.machine == machine_id for board in dataset.boards.values()):
            issues.append(
                Issue(
                    WARNING,
                    "machine-without-boards",
                    f"data/{machine_id}/machine.yaml",
                    "the machine has no board files",
                )
            )

    return issues


def check(dataset: Dataset) -> list[Issue]:
    """Every domain and integrity problem in the dataset."""
    issues: list[Issue] = []
    for board in dataset.boards.values():
        issues.extend(_check_board(board, dataset))
    issues.extend(_check_reference(dataset))
    return issues
