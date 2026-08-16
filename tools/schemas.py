"""Loading JSON Schemas and turning validation failures into issues."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.issues import ERROR, Issue

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


@cache
def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


def schema_issues(
    document: object, schema_name: str, location: str
) -> list[Issue]:
    """Validate one document, returning one issue per schema violation."""
    errors = sorted(
        _validator(schema_name).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    issues = []
    for error in errors:
        pointer = "/".join(str(part) for part in error.absolute_path) or "(root)"
        issues.append(
            Issue(
                level=ERROR,
                code="schema",
                location=f"{location}:{pointer}",
                message=error.message,
            )
        )
    return issues
