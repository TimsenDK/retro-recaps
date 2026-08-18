"""Domain rules and referential integrity.

These encode what the source material learned the hard way. Fit between a
part and a position is defined once, in ``tools.resolve``, and imported here
so validation and resolution can never disagree.
"""

import re
from collections import Counter

from tools.issues import ERROR, WARNING, Issue
from tools.model import Board, Dataset, Layout, Machine
from tools.resolve import fit_violations, same_capacitance

X2_MINIMUM_VOLTAGE_V = 275
"""A film-X2 capacitor sits across live and neutral. 275 VAC is the floor."""

Y2_MINIMUM_VOLTAGE_V = 250
"""A film-Y2 capacitor bridges the isolation barrier, line to earth.

Set from observed practice rather than read off the standard: IEC 60384-14's
own lower bound for the Y2 subclass is 150 V, which is far too permissive for
a 230 V line-to-earth position, and the normative table is behind a paywall.
Every currently stocked Y2 part surveyed carries 250 or 300 VAC. Y1 parts are
rated above Y2, so one floor covers both classes."""

MAINS_FILM_TYPES = ("film-x2", "film-y2")
"""The mains-rated film classes. Either satisfies ``x2_filter: listed``: the
field asks whether the input filter is inventoried, and an all-in-one Mac's
filter is Y-class across the isolation barrier rather than X-class across the
line."""

MAINS_DECISION_KINDS = ("psu", "analog")
"""Board kinds where whether the PCB carries mains must be stated outright.
Everything else defaults to not-mains, which is why the 1541 longboard
mainboard - a logic board with the machine's linear supply on it - carries an
explicit ``mains: true``."""

VERIFICATION_RANK = {"unverified": 0, "derived": 1, "verified": 2}
"""A position may be less certain than its board, never more."""

_FIT_NOTE_MEASUREMENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*mm\b", re.IGNORECASE)
"""A number immediately followed by 'mm' as a whole word, e.g. '24 mm'."""

FIT_NOTE_LIMIT_PHRASES = (
    "max",
    "maximum",
    "no more than",
    "not exceed",
    "under",
    "limited to",
    "no taller",
    "no higher",
    "clearance",
)
"""Heuristic and deliberately incomplete: a note that states a limit in words
none of these phrases anticipate is a false negative this list cannot close.
Extend it as real prose turns up rather than assuming it is exhaustive."""

_FIT_NOTE_LIMIT_RE = re.compile(
    "|".join(r"\b" + re.escape(phrase) + r"\b" for phrase in FIT_NOTE_LIMIT_PHRASES),
    re.IGNORECASE,
)


def _note_states_a_limit(note: str | None) -> bool:
    """Whether a note reads as a physical limit that no field enforces.

    Requires both a measurement (a number directly followed by 'mm', as a
    whole word) and a limit phrase (see FIT_NOTE_LIMIT_PHRASES) somewhere in
    the note, matched case-insensitively. The A500 rev 6A shield limit lived
    in prose for a while; this is what stops it going back there without also
    firing on 'Commodore' (which contains 'mm') or 'maxell' (which contains
    'max').
    """
    if note is None:
        return False
    return bool(_FIT_NOTE_MEASUREMENT_RE.search(note)) and bool(
        _FIT_NOTE_LIMIT_RE.search(note)
    )


def _board_location(board: Board) -> str:
    if board.path is not None:
        return board.path.as_posix()
    return board.id


def _machine_location(machine: Machine) -> str:
    if machine.path is not None:
        return machine.path.as_posix()
    return machine.id


def _layout_location(layout: Layout) -> str:
    if layout.path is not None:
        return layout.path.as_posix()
    return layout.id


def _check_layout(layout: Layout, dataset: Dataset) -> list[Issue]:
    """A map that disagrees with its board is worse than no map at all.

    A position the board does not list was invented. A position the board
    lists and the map omits is the dangerous one: it reads as "there is no
    capacitor there" to someone holding the board.
    """
    location = _layout_location(layout)
    issues: list[Issue] = []

    board = dataset.boards.get(layout.board)
    if board is None:
        return [
            Issue(
                ERROR,
                "layout-unknown-board",
                location,
                f"layout names board {layout.board!r}, which does not exist",
            )
        ]

    # A position with no named designators - whether it says so outright via
    # designators_unknown, or simply has an empty list - has nothing a map
    # could legitimately point to. One such position means the board as a
    # whole cannot be fully mapped without inventing a designator for it.
    if any(
        capacitor.designators_unknown or not capacitor.designators
        for capacitor in board.capacitors
    ):
        issues.append(
            Issue(
                ERROR,
                "layout-unmappable-board",
                location,
                "the board has positions with no named designators, so it "
                "cannot be mapped without inventing one",
            )
        )

    on_board = {
        designator
        for capacitor in board.capacitors
        for designator in capacitor.designators
    }
    placed = layout.designators

    for designator in sorted(placed - on_board):
        issues.append(
            Issue(
                ERROR,
                "layout-designator-not-on-board",
                location,
                f"the map places {designator}, which is not in the board's list",
            )
        )

    missing = sorted(on_board - placed)
    if missing:
        issues.append(
            Issue(
                ERROR,
                "layout-designator-missing",
                location,
                "the map leaves out positions the board lists: "
                + ", ".join(missing),
            )
        )

    # A frozenset only ever tells you which designators appear, never how
    # many times, so a copy-pasted feature that kept the old designator and
    # a new x/y collapses invisibly into the one already there. The renderer
    # then emits two `<g id="pos-C1">` elements at different coordinates,
    # and the highlight script's querySelector lights whichever it finds
    # first - a second, silently wrong dot on the map.
    designator_counts = Counter(
        feature.designator
        for feature in layout.features
        if feature.kind == "capacitor" and feature.designator
    )
    for designator, count in sorted(designator_counts.items()):
        if count > 1:
            issues.append(
                Issue(
                    ERROR,
                    "layout-duplicate-designator",
                    location,
                    f"{designator} is placed {count} times in this map; each "
                    f"designator must have exactly one position, or the "
                    f"drawing and the highlight script cannot tell which one "
                    f"is real",
                )
            )

    if layout.precision == "approximate" and layout.verification == "verified":
        issues.append(
            Issue(
                WARNING,
                "layout-approximate-but-verified",
                location,
                "positions read off a photograph are approximate; 'verified' "
                "means checked against a board",
            )
        )

    return issues


def _check_board(board: Board, dataset: Dataset) -> list[Issue]:
    issues: list[Issue] = []
    location = _board_location(board)

    if not board.sources:
        if board.verification == "verified":
            issues.append(
                Issue(
                    ERROR,
                    "verified-without-source",
                    location,
                    "verification is 'verified' but the board has no sources",
                )
            )
        else:
            for index, capacitor in enumerate(board.capacitors):
                if (
                    capacitor.effective_verification(board.verification)
                    != "verified"
                ):
                    continue
                issues.append(
                    Issue(
                        ERROR,
                        "verified-without-source",
                        f"{location}:capacitors/{index}",
                        "verification is 'verified' but the board has no sources",
                    )
                )
                break

    if not board.sources:
        # A stub asserts nothing, so it owes nothing. A board that publishes
        # positions and cites nothing is asking the reader to buy parts on
        # our word alone, which is exactly what this project exists not to do.
        if board.capacitors:
            issues.append(
                Issue(
                    ERROR,
                    "no-sources",
                    location,
                    "the board lists capacitor positions but cites no sources; "
                    "a published position needs a source a reader can retrieve",
                )
            )
        else:
            issues.append(
                Issue(WARNING, "no-sources", location, "the board cites no sources")
            )
    elif board.verification == "verified" and len(board.sources) < 2:
        issues.append(
            Issue(
                WARNING,
                "single-source-verified",
                location,
                "verification is 'verified' on a single source; nothing "
                "corroborates it if that source is wrong or unreadable",
            )
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

    # An 'unverified' board with no positions is the stub shape the schema
    # explicitly licenses: it exists to carry its open questions. Warning
    # about it is the validator arguing with the schema.
    if not board.capacitors and board.verification != "unverified":
        issues.append(
            Issue(
                WARNING,
                "no-capacitors",
                location,
                "the board lists no capacitor positions",
            )
        )

    if board.board in MAINS_DECISION_KINDS and board.mains is None:
        issues.append(
            Issue(
                ERROR,
                "mains-not-declared",
                location,
                f"a {board.board!r} board must declare 'mains' either way; the "
                f"board kind is not a reliable proxy for what the PCB carries",
            )
        )

    if board.carries_mains and board.x2_filter is None:
        issues.append(
            Issue(
                WARNING,
                "x2-filter-not-declared",
                location,
                "a mains-carrying board should declare 'x2_filter'; source "
                "silence about a mains film capacitor is not the same as its "
                "absence, and RIFA-style parts fail explosively",
            )
        )

    if board.x2_filter == "listed" and not any(
        capacitor.type in MAINS_FILM_TYPES for capacitor in board.capacitors
    ):
        issues.append(
            Issue(
                ERROR,
                "x2-filter-listed-but-absent",
                location,
                "x2_filter is 'listed' but the board has no mains film position; "
                "expected a film-x2 or film-y2 entry",
            )
        )

    if board.x2_filter is not None and not board.carries_mains:
        issues.append(
            Issue(
                ERROR,
                "x2-filter-off-mains",
                location,
                "x2_filter describes a mains input filter, but this board is "
                "not declared as mains-carrying",
            )
        )

    seen: dict[str, int] = {}
    for capacitor in board.capacitors:
        for designator in capacitor.designators:
            seen[designator] = seen.get(designator, 0) + 1
    for designator, count in seen.items():
        if count > 1:
            issues.append(
                Issue(
                    ERROR,
                    "duplicate-designator",
                    location,
                    f"designator {designator!r} appears {count} times on this "
                    f"board; each position belongs to exactly one entry",
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

        if (
            capacitor.original_voltage_v is None
            and not capacitor.original_voltage_unknown
        ):
            issues.append(
                Issue(
                    WARNING,
                    "no-original-voltage",
                    where,
                    "the position records no original_voltage_v, so the "
                    "voltage rule cannot be checked here; record the factory "
                    "rating or declare original_voltage_unknown",
                )
            )

        if (
            capacitor.type == "film-x2"
            and capacitor.voltage_v < X2_MINIMUM_VOLTAGE_V
        ):
            issues.append(
                Issue(
                    ERROR,
                    "x2-voltage-too-low",
                    where,
                    f"{capacitor.voltage_v} V is below the {X2_MINIMUM_VOLTAGE_V} V "
                    f"minimum for a film-x2 part; this is a mains-rated position "
                    f"across live and neutral",
                )
            )

        if (
            capacitor.type == "film-y2"
            and capacitor.voltage_v < Y2_MINIMUM_VOLTAGE_V
        ):
            issues.append(
                Issue(
                    ERROR,
                    "y2-voltage-too-low",
                    where,
                    f"{capacitor.voltage_v} V is below the {Y2_MINIMUM_VOLTAGE_V} V "
                    f"minimum for a film-y2 part; this is a mains-rated position "
                    f"bridging the isolation barrier",
                )
            )

        if not capacitor.designators:
            if not capacitor.designators_unknown:
                issues.append(
                    Issue(
                        WARNING,
                        "no-designators",
                        where,
                        "the position has no reference designators; list them "
                        "or declare designators_unknown",
                    )
                )
        elif len(capacitor.designators) != capacitor.quantity:
            issues.append(
                Issue(
                    ERROR,
                    "quantity-designator-mismatch",
                    where,
                    f"quantity is {capacitor.quantity} but "
                    f"{len(capacitor.designators)} designators are listed",
                )
            )

        if capacitor.verification is not None and VERIFICATION_RANK.get(
            capacitor.verification, 0
        ) > VERIFICATION_RANK.get(board.verification, 0):
            issues.append(
                Issue(
                    ERROR,
                    "position-over-verified",
                    where,
                    f"the position claims {capacitor.verification!r} on a board "
                    f"that is only {board.verification!r}; a position may be "
                    f"less certain than its board, never more",
                )
            )

        # Without one of these the site has nothing to recommend, and a
        # position nobody can buy a part for is usually a position that does
        # not exist.
        if capacitor.series is None and capacitor.part is None:
            issues.append(
                Issue(
                    ERROR,
                    "no-series-or-part",
                    where,
                    "the position names neither a series nor a part, so no "
                    "replacement can be recommended for it",
                )
            )

        if capacitor.series is not None:
            series = dataset.series.get(capacitor.series)
            if series is None:
                issues.append(
                    Issue(
                        ERROR,
                        "unknown-series",
                        where,
                        f"series {capacitor.series!r} is not defined",
                    )
                )
            elif series.type != capacitor.type:
                issues.append(
                    Issue(
                        ERROR,
                        "series-type-mismatch",
                        where,
                        f"series {series.id!r} is {series.type}, the position is "
                        f"{capacitor.type}",
                    )
                )
            elif not series.covers(capacitor.voltage_v):
                # Nothing else catches this: the series exists, it is the right
                # type, and the position validates - it just sends the reader
                # to a catalogue page that does not stock the rating.
                issues.append(
                    Issue(
                        ERROR,
                        "series-voltage-out-of-range",
                        where,
                        f"series {series.id!r} is made in {series.voltage_range} "
                        f"and the position is {capacitor.voltage_v} V; no part "
                        f"of this series fits it",
                    )
                )

        stated_limits = (
            capacitor.max_height_mm,
            capacitor.max_diameter_mm,
            capacitor.max_lead_spacing_mm,
        )
        if _note_states_a_limit(capacitor.note) and all(
            limit is None for limit in stated_limits
        ):
            issues.append(
                Issue(
                    WARNING,
                    "unenforceable-fit-note",
                    where,
                    "the note states a physical limit but the position declares "
                    "no max_height_mm, max_diameter_mm or max_lead_spacing_mm, "
                    "so nothing enforces it",
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

        mismatched = False
        if part.type != capacitor.type:
            mismatched = True
            issues.append(
                Issue(
                    ERROR,
                    "part-mismatch",
                    where,
                    f"pinned part {part.id!r} is {part.type}, the position is "
                    f"{capacitor.type}",
                )
            )
        if not same_capacitance(part.capacitance_uf, capacitor.capacitance_uf):
            mismatched = True
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
            mismatched = True
            issues.append(
                Issue(
                    ERROR,
                    "part-mismatch",
                    where,
                    f"pinned part {part.id!r} is rated {part.voltage_v} V, below "
                    f"the position's {capacitor.voltage_v} V",
                )
            )

        # The wrong part is the wrong part; its dimensions are beside the
        # point, and reporting both would read as contradictory advice.
        if mismatched:
            continue

        for label, value, limit in fit_violations(part, capacitor):
            issues.append(
                Issue(
                    ERROR,
                    "part-does-not-fit",
                    where,
                    f"pinned part {part.id!r} has a {label} of {value} mm, above "
                    f"the position's limit of {limit} mm",
                )
            )

    return issues


def _check_reference(dataset: Dataset) -> list[Issue]:
    issues: list[Issue] = []

    for part in dataset.parts.values():
        series = dataset.series.get(part.series)
        if series is None:
            issues.append(
                Issue(
                    ERROR,
                    "unknown-series",
                    f"reference/parts.yaml:{part.id}",
                    f"series {part.series!r} is not defined",
                )
            )
        elif series.type != part.type:
            issues.append(
                Issue(
                    ERROR,
                    "series-type-mismatch",
                    f"reference/parts.yaml:{part.id}",
                    f"series {series.id!r} is {series.type}, the part is "
                    f"{part.type}",
                )
            )
        elif not series.covers(part.voltage_v):
            issues.append(
                Issue(
                    ERROR,
                    "series-voltage-out-of-range",
                    f"reference/parts.yaml:{part.id}",
                    f"series {series.id!r} is made in {series.voltage_range} "
                    f"and the part is rated {part.voltage_v} V",
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

    # Two board files of one machine and one board kind claiming the same
    # revision leaves the reader unable to tell which list applies to the
    # board in front of them.
    claimed: dict[tuple[str, str, str], list[str]] = {}
    for board in dataset.boards.values():
        for revision in board.revisions:
            key = (board.machine, board.board, revision)
            claimed.setdefault(key, []).append(_board_location(board))
    for (machine_id, kind, revision), locations in claimed.items():
        if len(locations) < 2:
            continue
        for location in sorted(locations):
            issues.append(
                Issue(
                    ERROR,
                    "duplicate-revision",
                    location,
                    f"revision {revision!r} of the {machine_id} {kind} is also "
                    f"claimed by "
                    + ", ".join(other for other in sorted(locations) if other != location),
                )
            )

    # Two layout files naming the same board is not a mistake either file
    # would raise on its own: each can place every designator the board
    # lists and validate cleanly by itself. layouts_by_board then keeps
    # only the last one it sees, so the other's positions never reach a
    # page - a stale layout can silently override a corrected one, and
    # nothing on the site or in this report would say so without this check.
    claimed_boards: dict[str, list[Layout]] = {}
    for layout in dataset.layouts.values():
        claimed_boards.setdefault(layout.board, []).append(layout)
    for board_id, layouts in claimed_boards.items():
        if len(layouts) < 2:
            continue
        ids = sorted(layout.id for layout in layouts)
        for layout in sorted(layouts, key=_layout_location):
            others = ", ".join(i for i in ids if i != layout.id)
            issues.append(
                Issue(
                    ERROR,
                    "layout-duplicate-board",
                    _layout_location(layout),
                    f"board {board_id!r} is also claimed by layout "
                    + others,
                )
            )

    # A machine with a cell whose boards all stay silent about it means the
    # warning reaches nobody's printed board sheet. The inverse - a board
    # claiming a battery its machine does not record - is a contradiction.
    for machine_id, machine in dataset.machines.items():
        boards = [b for b in dataset.boards.values() if b.machine == machine_id]
        if machine.batteries and not any(board.battery for board in boards):
            issues.append(
                Issue(
                    WARNING,
                    "battery-on-no-board",
                    _machine_location(machine),
                    "the machine records a battery but no board declares "
                    "'battery: true', so no board sheet carries the warning",
                )
            )
        if not machine.batteries:
            for board in boards:
                if not board.battery:
                    continue
                issues.append(
                    Issue(
                        ERROR,
                        "battery-without-machine",
                        _board_location(board),
                        f"the board declares a battery but machine "
                        f"{machine_id!r} records none",
                    )
                )

    for machine_id, machine in dataset.machines.items():
        if machine.path is not None:
            parent = machine.path.parent.name
            if parent and parent != machine.id:
                issues.append(
                    Issue(
                        ERROR,
                        "id-path-mismatch",
                        _machine_location(machine),
                        f"the machine sits in {parent!r} but declares id "
                        f"{machine.id!r}",
                    )
                )
        if not any(board.machine == machine_id for board in dataset.boards.values()):
            issues.append(
                Issue(
                    WARNING,
                    "machine-without-boards",
                    _machine_location(machine),
                    "the machine has no board files",
                )
            )

    return issues


def check(dataset: Dataset) -> list[Issue]:
    """Every domain and integrity problem in the dataset."""
    issues: list[Issue] = []
    for board in dataset.boards.values():
        issues.extend(_check_board(board, dataset))
    for layout in dataset.layouts.values():
        issues.extend(_check_layout(layout, dataset))
    issues.extend(_check_reference(dataset))
    return issues
