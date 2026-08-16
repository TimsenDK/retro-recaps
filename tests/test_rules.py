from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset
from tools.model import Board, Dataset, Machine, Part, Series
from tools.rules import check

FIXTURES = Path(__file__).parent / "fixtures"


def codes(dataset: Dataset) -> set[str]:
    return {issue.code for issue in check(dataset)}


def make_dataset(board_document: dict, **overrides) -> Dataset:
    machine = Machine.from_dict(
        {
            "id": "amiga-500",
            "name": "Commodore Amiga 500",
            "family": "amiga",
            "board_order": ["mainboard"],
        }
    )
    board = Board.from_dict(
        board_document, path=Path("data/amiga-500/mainboard-rev6a.yaml")
    )
    base = {
        "machines": {machine.id: machine},
        "boards": {board.id: board},
        "parts": {},
        "series": {},
        "suppliers": {},
        "offers": {},
    }
    return Dataset(**{**base, **overrides})


def board_document(**overrides) -> dict:
    base = {
        "id": "amiga-500-mainboard-rev6a",
        "machine": "amiga-500",
        "board": "mainboard",
        "revisions": ["6A"],
        "verification": "unverified",
        "capacitors": [
            {
                "designators": ["C401"],
                "type": "electrolytic-radial",
                "capacitance_uf": 3300,
                "voltage_v": 25,
                "quantity": 1,
            }
        ],
    }
    return {**base, **overrides}


def test_the_good_fixture_passes_cleanly() -> None:
    dataset, load_issues = load_dataset(FIXTURES / "good")
    assert load_issues == []
    errors = [issue for issue in check(dataset) if issue.level == "error"]
    assert errors == []


def test_voltage_downgrade_is_an_error() -> None:
    document = board_document()
    document["capacitors"][0]["original_voltage_v"] = 35
    assert "voltage-downgrade" in codes(make_dataset(document))


def test_voltage_upgrade_is_fine() -> None:
    document = board_document()
    document["capacitors"][0]["original_voltage_v"] = 16
    assert "voltage-downgrade" not in codes(make_dataset(document))


def test_verified_without_a_source_is_an_error() -> None:
    document = board_document(verification="verified")
    assert "verified-without-source" in codes(make_dataset(document))


def test_id_must_match_the_path() -> None:
    document = board_document(id="amiga-500-mainboard-rev8a")
    assert "id-path-mismatch" in codes(make_dataset(document))


def test_unknown_machine_is_an_error() -> None:
    document = board_document(machine="amiga-4000")
    assert "unknown-machine" in codes(make_dataset(document))


def test_board_kind_outside_the_recap_order_is_an_error() -> None:
    document = board_document(board="psu")
    assert "board-kind-not-ordered" in codes(make_dataset(document))


def test_unknown_series_is_an_error() -> None:
    document = board_document()
    document["capacitors"][0]["series"] = "nichicon-hz"
    assert "unknown-series" in codes(make_dataset(document))


def test_unknown_pinned_part_is_an_error() -> None:
    document = board_document()
    document["capacitors"][0]["part"] = "not-a-part"
    assert "unknown-part" in codes(make_dataset(document))


def test_pinned_part_with_too_low_a_voltage_is_an_error() -> None:
    part = Part.from_dict(
        {
            "id": "weak",
            "manufacturer": "Panasonic",
            "mpn": "X",
            "series": "panasonic-fr",
            "type": "electrolytic-radial",
            "capacitance_uf": 3300,
            "voltage_v": 16,
        }
    )
    series = Series.from_dict(
        {
            "id": "panasonic-fr",
            "manufacturer": "Panasonic",
            "name": "FR",
            "type": "electrolytic-radial",
        }
    )
    document = board_document()
    document["capacitors"][0]["part"] = "weak"
    dataset = make_dataset(
        document, parts={"weak": part}, series={"panasonic-fr": series}
    )
    assert "part-mismatch" in codes(dataset)


def test_pinned_part_with_the_wrong_capacitance_is_an_error() -> None:
    part = Part.from_dict(
        {
            "id": "wrong",
            "manufacturer": "Panasonic",
            "mpn": "X",
            "series": "panasonic-fr",
            "type": "electrolytic-radial",
            "capacitance_uf": 470,
            "voltage_v": 25,
        }
    )
    series = Series.from_dict(
        {
            "id": "panasonic-fr",
            "manufacturer": "Panasonic",
            "name": "FR",
            "type": "electrolytic-radial",
        }
    )
    document = board_document()
    document["capacitors"][0]["part"] = "wrong"
    dataset = make_dataset(
        document, parts={"wrong": part}, series={"panasonic-fr": series}
    )
    assert "part-mismatch" in codes(dataset)


def test_missing_sources_is_only_a_warning() -> None:
    issues = check(make_dataset(board_document()))
    no_sources = [issue for issue in issues if issue.code == "no-sources"]
    assert len(no_sources) == 1
    assert no_sources[0].level == "warning"


def test_missing_designators_is_a_warning() -> None:
    document = board_document()
    del document["capacitors"][0]["designators"]
    issues = check(make_dataset(document))
    assert any(
        issue.code == "no-designators" and issue.level == "warning" for issue in issues
    )


def test_unknown_offer_supplier_is_an_error() -> None:
    dataset = make_dataset(board_document(), offers={"ghost": {"eeufr1e332": "1"}})
    assert "unknown-offer-supplier" in codes(dataset)


def test_machine_without_boards_is_a_warning() -> None:
    machine = Machine.from_dict(
        {
            "id": "amiga-500",
            "name": "Commodore Amiga 500",
            "family": "amiga",
            "board_order": ["mainboard"],
        }
    )
    dataset = Dataset(
        machines={"amiga-500": machine},
        boards={},
        parts={},
        series={},
        suppliers={},
        offers={},
    )
    assert "machine-without-boards" in codes(dataset)
