"""Reading the YAML tree into a Dataset."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml

from tools.issues import ERROR, Issue
from tools.model import Board, Dataset, Machine, Part, Series, Supplier
from tools.schemas import schema_issues


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read(path: Path, root: Path, issues: list[Issue]) -> object | None:
    """Parse one YAML file, recording a problem rather than raising."""
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as error:
        issues.append(
            Issue(
                ERROR,
                "yaml",
                _relative(path, root),
                str(error).replace("\n", " "),
            )
        )
    except OSError as error:
        issues.append(Issue(ERROR, "unreadable", _relative(path, root), str(error)))
    return None


def _checked(
    path: Path, root: Path, schema_name: str, issues: list[Issue]
) -> object | None:
    document = _read(path, root, issues)
    if document is None:
        return None
    location = _relative(path, root)
    violations = schema_issues(document, schema_name, location)
    if violations:
        issues.extend(violations)
        return None
    return document


def _load_machines_and_boards(
    root: Path, issues: list[Issue]
) -> tuple[dict[str, Machine], dict[str, Board]]:
    machines: dict[str, Machine] = {}
    boards: dict[str, Board] = {}
    data_dir = root / "data"
    if not data_dir.is_dir():
        return machines, boards

    for machine_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        if machine_dir.name.startswith("_"):
            continue
        for path in sorted(machine_dir.glob("*.yaml")):
            if path.name == "machine.yaml":
                document = _checked(path, root, "machine", issues)
                if document is None:
                    continue
                machine = Machine.from_dict(document)
                if machine.id in machines:
                    issues.append(
                        Issue(
                            ERROR,
                            "duplicate-id",
                            _relative(path, root),
                            f"machine id {machine.id!r} is already defined",
                        )
                    )
                    continue
                machines[machine.id] = machine
            else:
                document = _checked(path, root, "board", issues)
                if document is None:
                    continue
                board = Board.from_dict(document, path=path)
                if board.id in boards:
                    issues.append(
                        Issue(
                            ERROR,
                            "duplicate-id",
                            _relative(path, root),
                            f"board id {board.id!r} is already defined",
                        )
                    )
                    continue
                boards[board.id] = board

    return machines, boards


def _load_list(
    root: Path,
    name: str,
    schema_name: str,
    factory: Callable[[object], object],
    issues: list[Issue],
) -> dict:
    path = root / "reference" / f"{name}.yaml"
    if not path.is_file():
        return {}
    document = _checked(path, root, schema_name, issues)
    if document is None:
        return {}
    result: dict = {}
    for item in document:
        entry = factory(item)
        if entry.id in result:
            issues.append(
                Issue(
                    ERROR,
                    "duplicate-id",
                    _relative(path, root),
                    f"{name} id {entry.id!r} is already defined",
                )
            )
            continue
        result[entry.id] = entry
    return result


def _load_offers(root: Path, issues: list[Issue]) -> dict[str, dict[str, str]]:
    offers_dir = root / "reference" / "offers"
    if not offers_dir.is_dir():
        return {}
    offers: dict[str, dict[str, str]] = {}
    for path in sorted(offers_dir.glob("*.yaml")):
        document = _checked(path, root, "offers", issues)
        if document is None:
            continue
        offers[path.stem] = dict(document)
    return offers


def load_dataset(root: Path) -> tuple[Dataset, list[Issue]]:
    """Load everything under root, collecting problems instead of raising."""
    issues: list[Issue] = []
    machines, boards = _load_machines_and_boards(root, issues)
    dataset = Dataset(
        machines=machines,
        boards=boards,
        parts=_load_list(root, "parts", "parts", Part.from_dict, issues),
        series=_load_list(root, "series", "series", Series.from_dict, issues),
        suppliers=_load_list(
            root, "suppliers", "suppliers", Supplier.from_dict, issues
        ),
        offers=_load_offers(root, issues),
    )
    return dataset, issues
