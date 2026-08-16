from __future__ import annotations

from tools.issues import Issue, count_by_level, format_report


def test_counts_by_level() -> None:
    issues = [
        Issue("error", "schema", "a.yaml", "bad"),
        Issue("warning", "no-sources", "b.yaml", "meh"),
        Issue("error", "voltage-downgrade", "c.yaml", "worse"),
    ]
    assert count_by_level(issues) == {"error": 2, "warning": 1}


def test_empty_report_says_so() -> None:
    assert format_report([]) == "No problems found."


def test_report_groups_errors_before_warnings() -> None:
    issues = [
        Issue("warning", "no-sources", "b.yaml", "no sources"),
        Issue("error", "schema", "a.yaml", "missing field"),
    ]
    report = format_report(issues)
    lines = report.splitlines()
    assert lines[0] == "ERROR  a.yaml  [schema] missing field"
    assert lines[1] == "WARN   b.yaml  [no-sources] no sources"
    assert lines[-1] == "1 error, 1 warning"


def test_summary_pluralises() -> None:
    issues = [
        Issue("error", "schema", "a.yaml", "one"),
        Issue("error", "schema", "b.yaml", "two"),
    ]
    assert format_report(issues).splitlines()[-1] == "2 errors, 0 warnings"
