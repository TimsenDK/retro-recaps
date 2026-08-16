from __future__ import annotations

from tools.schemas import load_schema, schema_issues

VALID_BOARD = {
    "id": "amiga-500-mainboard-rev6a",
    "machine": "amiga-500",
    "board": "mainboard",
    "revisions": ["6A"],
    "verification": "verified",
    "sources": [{"url": "https://example.invalid/a500", "note": "with designators"}],
    "capacitors": [
        {
            "designators": ["C401", "C402"],
            "type": "electrolytic-radial",
            "capacitance_uf": 3300,
            "voltage_v": 25,
            "original_voltage_v": 16,
            "quantity": 2,
            "series": "panasonic-fr",
        }
    ],
}


def test_every_schema_loads() -> None:
    for name in ("machine", "board", "series", "parts", "suppliers", "offers"):
        assert load_schema(name)["$schema"].endswith("2020-12/schema")


def test_valid_board_produces_no_issues() -> None:
    assert schema_issues(VALID_BOARD, "board", "a.yaml") == []


def test_missing_required_field_is_an_error() -> None:
    document = {key: value for key, value in VALID_BOARD.items() if key != "machine"}
    issues = schema_issues(document, "board", "a.yaml")
    assert len(issues) == 1
    assert issues[0].level == "error"
    assert issues[0].code == "schema"
    assert issues[0].location == "a.yaml:(root)"


def test_unknown_capacitor_type_is_an_error() -> None:
    document = {**VALID_BOARD}
    document["capacitors"] = [{**VALID_BOARD["capacitors"][0], "type": "ceramic"}]
    issues = schema_issues(document, "board", "a.yaml")
    assert [issue.location for issue in issues] == ["a.yaml:capacitors/0/type"]


def test_unknown_property_is_rejected() -> None:
    issues = schema_issues({**VALID_BOARD, "colour": "beige"}, "board", "a.yaml")
    assert len(issues) == 1


def test_a_placeholder_source_url_is_rejected() -> None:
    document = {**VALID_BOARD, "sources": [{"url": "http://x"}]}
    issues = schema_issues(document, "board", "a.yaml")
    assert [issue.location for issue in issues] == ["a.yaml:sources/0/url"]


def test_a_url_that_is_not_a_uri_at_all_is_rejected() -> None:
    # Matches the schema's `pattern`, so only the `format: uri` checker can
    # reject it: '[' is not a legal character outside an IPv6 host literal.
    document = {**VALID_BOARD, "sources": [{"url": "https://ex[ample.com/x"}]}
    assert schema_issues(document, "board", "a.yaml")


def test_a_real_source_url_is_accepted() -> None:
    document = {
        **VALID_BOARD,
        "sources": [{"url": "https://support.retrorewind.ca/amiga/a500?rev=6a#c401"}],
    }
    assert schema_issues(document, "board", "a.yaml") == []


def test_an_unverified_board_may_list_no_capacitors() -> None:
    document = {
        **VALID_BOARD,
        "verification": "unverified",
        "capacitors": [],
    }
    assert schema_issues(document, "board", "a.yaml") == []


def test_a_verified_board_may_not_list_no_capacitors() -> None:
    document = {**VALID_BOARD, "capacitors": []}
    assert schema_issues(document, "board", "a.yaml")


def test_a_derived_board_may_not_list_no_capacitors() -> None:
    document = {**VALID_BOARD, "verification": "derived", "capacitors": []}
    assert schema_issues(document, "board", "a.yaml")


def test_an_empty_document_is_not_a_board() -> None:
    assert schema_issues(None, "board", "a.yaml")


def test_quantity_must_be_positive() -> None:
    document = {**VALID_BOARD}
    document["capacitors"] = [{**VALID_BOARD["capacitors"][0], "quantity": 0}]
    assert schema_issues(document, "board", "a.yaml")
