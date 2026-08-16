"""Problems found while validating the dataset."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

ERROR = "error"
WARNING = "warning"

_LEVEL_ORDER = {ERROR: 0, WARNING: 1}
_LEVEL_LABEL = {ERROR: "ERROR ", WARNING: "WARN  "}


@dataclass(frozen=True)
class Issue:
    """One problem, at one location, with a stable machine-readable code."""

    level: str
    code: str
    location: str
    message: str


def count_by_level(issues: Sequence[Issue]) -> dict[str, int]:
    counts = {ERROR: 0, WARNING: 0}
    for issue in issues:
        counts[issue.level] = counts.get(issue.level, 0) + 1
    return counts


def _sort_key(issue: Issue) -> tuple[int, str, str]:
    return (_LEVEL_ORDER.get(issue.level, 9), issue.location, issue.code)


def format_report(issues: Sequence[Issue]) -> str:
    if not issues:
        return "No problems found."

    lines = [
        f"{_LEVEL_LABEL.get(issue.level, issue.level)} {issue.location}"
        f"  [{issue.code}] {issue.message}"
        for issue in sorted(issues, key=_sort_key)
    ]

    counts = count_by_level(issues)
    errors = counts.get(ERROR, 0)
    warnings = counts.get(WARNING, 0)
    lines.append(
        f"{errors} {'error' if errors == 1 else 'errors'}, "
        f"{warnings} {'warning' if warnings == 1 else 'warnings'}"
    )
    return "\n".join(lines)
