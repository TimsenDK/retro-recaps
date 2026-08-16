"""The validate command."""

from __future__ import annotations

from pathlib import Path

from tools.issues import ERROR, WARNING, count_by_level, format_report
from tools.loader import load_dataset
from tools.rules import check


def run_validate(root: Path, strict: bool = False) -> int:
    dataset, issues = load_dataset(root)
    issues = issues + check(dataset)

    print(format_report(issues))

    counts = count_by_level(issues)
    if counts.get(ERROR, 0):
        return 1
    if strict and counts.get(WARNING, 0):
        return 1
    return 0
