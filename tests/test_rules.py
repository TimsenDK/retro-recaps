from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset
from tools.model import Board, Dataset, Machine, Part, Series, Supplier
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


def fitting_part(**overrides) -> Part:
    base = {
        "id": "big",
        "manufacturer": "Panasonic",
        "mpn": "X",
        "series": "panasonic-fr",
        "type": "electrolytic-radial",
        "capacitance_uf": 3300,
        "voltage_v": 25,
        "diameter_mm": 12.5,
        "height_mm": 20,
        "lead_spacing_mm": 5,
    }
    return Part.from_dict({**base, **overrides})


def pinned_dataset(part: Part, **capacitor_fields) -> Dataset:
    series = Series.from_dict(series_document())
    document = board_document()
    document["capacitors"][0].update({"part": part.id, **capacitor_fields})
    return make_dataset(
        document, parts={part.id: part}, series={"panasonic-fr": series}
    )


def fit_issues(dataset: Dataset) -> list:
    return [issue for issue in check(dataset) if issue.code == "part-does-not-fit"]


def test_a_pinned_part_that_is_too_tall_does_not_fit() -> None:
    dataset = pinned_dataset(fitting_part(), max_height_mm=15)
    issues = fit_issues(dataset)
    assert len(issues) == 1
    assert issues[0].level == "error"
    assert "height" in issues[0].message
    assert "20" in issues[0].message and "15" in issues[0].message


def test_a_pinned_part_that_is_too_wide_does_not_fit() -> None:
    issues = fit_issues(pinned_dataset(fitting_part(), max_diameter_mm=10))
    assert len(issues) == 1
    assert "diameter" in issues[0].message


def test_a_pinned_part_with_too_wide_a_lead_spacing_does_not_fit() -> None:
    issues = fit_issues(pinned_dataset(fitting_part(), max_lead_spacing_mm=3.5))
    assert len(issues) == 1
    assert "lead spacing" in issues[0].message


def test_a_pinned_part_within_every_limit_fits() -> None:
    dataset = pinned_dataset(
        fitting_part(),
        max_height_mm=20,
        max_diameter_mm=12.5,
        max_lead_spacing_mm=5,
    )
    assert "part-does-not-fit" not in codes(dataset)


def test_a_pinned_part_of_unknown_height_is_not_a_fit_error() -> None:
    """The catalogue may be incomplete; that is not the board file's fault."""
    part = Part.from_dict(
        {
            "id": "unmeasured",
            "manufacturer": "Panasonic",
            "mpn": "X",
            "series": "panasonic-fr",
            "type": "electrolytic-radial",
            "capacitance_uf": 3300,
            "voltage_v": 25,
        }
    )
    dataset = pinned_dataset(part, max_height_mm=5)
    assert "part-does-not-fit" not in codes(dataset)


def test_a_fit_error_is_not_reported_as_a_part_mismatch() -> None:
    """The Status page must tell 'wrong part' from 'right part, will not fit'."""
    dataset = pinned_dataset(fitting_part(), max_height_mm=15)
    assert "part-does-not-fit" in codes(dataset)
    assert "part-mismatch" not in codes(dataset)


def test_a_wrong_part_is_not_also_reported_as_not_fitting() -> None:
    part = fitting_part(capacitance_uf=470)
    dataset = pinned_dataset(part, max_height_mm=15)
    assert "part-mismatch" in codes(dataset)
    assert "part-does-not-fit" not in codes(dataset)


def fit_note_warning_codes(note: str) -> set[str]:
    document = board_document()
    document["capacitors"][0]["note"] = note
    return codes(make_dataset(document))


def test_a_note_stating_a_limit_without_a_field_is_a_warning() -> None:
    document = board_document()
    document["capacitors"][0]["note"] = "Maximum height 24 mm."
    issues = [
        issue
        for issue in check(make_dataset(document))
        if issue.code == "unenforceable-fit-note"
    ]
    assert len(issues) == 1
    assert issues[0].level == "warning"


def test_a_note_stating_a_limit_alongside_a_field_is_fine() -> None:
    document = board_document()
    document["capacitors"][0]["note"] = "Maximum height 24 mm."
    document["capacitors"][0]["max_height_mm"] = 24
    assert "unenforceable-fit-note" not in codes(make_dataset(document))


def test_an_ordinary_note_raises_no_fit_warning() -> None:
    document = board_document()
    document["capacitors"][0]["note"] = "Radial in the original, axial on rev 3."
    assert "unenforceable-fit-note" not in codes(make_dataset(document))


def test_a_note_without_a_unit_raises_no_fit_warning() -> None:
    document = board_document()
    document["capacitors"][0]["note"] = "Maximum ripple current matters here."
    assert "unenforceable-fit-note" not in codes(make_dataset(document))


def test_the_canonical_board_level_shield_note_now_warns() -> None:
    """This is the exact prose from the A500 rev 6A fixture's board note.

    It must warn, or a contributor who has seen the warning fire once will
    read silence as 'no unenforced limit here', which would be wrong.
    """
    note = "C401 and C402 must not exceed 24 mm in height because of the shield."
    assert "unenforceable-fit-note" in fit_note_warning_codes(note)


def test_a_note_stating_a_limit_is_by_the_shield_warns() -> None:
    note = "Height limited to 24 mm by the shield."
    assert "unenforceable-fit-note" in fit_note_warning_codes(note)


def test_a_note_saying_must_be_under_a_height_warns() -> None:
    note = "Must be under 24 mm tall."
    assert "unenforceable-fit-note" in fit_note_warning_codes(note)


def test_a_note_saying_no_taller_than_warns() -> None:
    note = "No taller than 24 mm."
    assert "unenforceable-fit-note" in fit_note_warning_codes(note)


def test_a_limit_phrase_without_a_measurement_raises_no_fit_warning() -> None:
    """'maximum' alone, with no 'mm' measurement, is not an enforceable limit."""
    note = "Commodore used the maximum voltage variant."
    assert "unenforceable-fit-note" not in fit_note_warning_codes(note)


def test_an_unrelated_note_about_part_provenance_raises_no_fit_warning() -> None:
    note = "Originally a Frako; check polarity before fitting."
    assert "unenforceable-fit-note" not in fit_note_warning_codes(note)


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


def test_unknown_offer_part_is_an_error() -> None:
    supplier = Supplier.from_dict(
        {
            "id": "mouser",
            "name": "Mouser",
            "search_url": "https://www.mouser.com/c/?q={query}",
        }
    )
    dataset = make_dataset(
        board_document(),
        suppliers={"mouser": supplier},
        offers={"mouser": {"not-a-part": "1"}},
    )
    assert "unknown-offer-part" in codes(dataset)
    assert "unknown-offer-supplier" not in codes(dataset)


def test_verified_position_without_a_source_is_an_error() -> None:
    document = board_document(verification="unverified")
    document["capacitors"][0]["verification"] = "verified"
    assert "verified-without-source" in codes(make_dataset(document))


def test_derived_or_unverified_positions_without_a_source_is_fine() -> None:
    document = board_document(verification="unverified")
    document["capacitors"][0]["verification"] = "derived"
    document["capacitors"].append(
        {
            "designators": ["C402"],
            "type": "electrolytic-radial",
            "capacitance_uf": 100,
            "voltage_v": 16,
            "quantity": 1,
            "verification": "unverified",
        }
    )
    assert "verified-without-source" not in codes(make_dataset(document))


def series_document(**overrides) -> dict:
    base = {
        "id": "panasonic-fr",
        "manufacturer": "Panasonic",
        "name": "FR",
        "type": "electrolytic-radial",
    }
    return {**base, **overrides}


def test_a_film_x2_below_275v_is_an_error() -> None:
    document = board_document()
    document["capacitors"][0].update(
        {"type": "film-x2", "capacitance_uf": 0.1, "voltage_v": 25}
    )
    issues = check(make_dataset(document))
    too_low = [issue for issue in issues if issue.code == "x2-voltage-too-low"]
    assert len(too_low) == 1
    assert too_low[0].level == "error"
    assert "275" in too_low[0].message


def test_a_film_x2_at_275v_is_fine() -> None:
    document = board_document()
    document["capacitors"][0].update(
        {"type": "film-x2", "capacitance_uf": 0.1, "voltage_v": 275}
    )
    assert "x2-voltage-too-low" not in codes(make_dataset(document))


def test_a_low_voltage_electrolytic_is_not_an_x2_problem() -> None:
    document = board_document()
    document["capacitors"][0]["voltage_v"] = 25
    assert "x2-voltage-too-low" not in codes(make_dataset(document))


def test_a_polarised_series_on_a_bipolar_position_is_an_error() -> None:
    series = Series.from_dict(series_document())
    document = board_document()
    document["capacitors"][0].update({"type": "bipolar", "series": "panasonic-fr"})
    dataset = make_dataset(document, series={"panasonic-fr": series})
    assert "series-type-mismatch" in codes(dataset)


def test_a_bipolar_series_on_a_polarised_position_is_an_error() -> None:
    series = Series.from_dict(
        series_document(id="nichicon-ues", name="UES", type="bipolar")
    )
    document = board_document()
    document["capacitors"][0]["series"] = "nichicon-ues"
    dataset = make_dataset(document, series={"nichicon-ues": series})
    assert "series-type-mismatch" in codes(dataset)


def test_a_matching_series_on_a_position_is_fine() -> None:
    series = Series.from_dict(series_document())
    document = board_document()
    document["capacitors"][0]["series"] = "panasonic-fr"
    dataset = make_dataset(document, series={"panasonic-fr": series})
    assert "series-type-mismatch" not in codes(dataset)


def test_a_part_whose_series_is_of_another_type_is_an_error() -> None:
    part = Part.from_dict(
        {
            "id": "wrong-family",
            "manufacturer": "Nichicon",
            "mpn": "X",
            "series": "nichicon-ues",
            "type": "electrolytic-radial",
            "capacitance_uf": 47,
            "voltage_v": 25,
        }
    )
    series = Series.from_dict(
        series_document(id="nichicon-ues", name="UES", type="bipolar")
    )
    dataset = make_dataset(
        board_document(),
        parts={"wrong-family": part},
        series={"nichicon-ues": series},
    )
    assert "series-type-mismatch" in codes(dataset)


def test_a_missing_original_voltage_is_a_warning() -> None:
    issues = check(make_dataset(board_document()))
    missing = [issue for issue in issues if issue.code == "no-original-voltage"]
    assert len(missing) == 1
    assert missing[0].level == "warning"


def test_a_recorded_original_voltage_raises_no_warning() -> None:
    document = board_document()
    document["capacitors"][0]["original_voltage_v"] = 16
    assert "no-original-voltage" not in codes(make_dataset(document))


def test_designator_count_must_equal_quantity() -> None:
    document = board_document()
    document["capacitors"][0]["designators"] = ["C401", "C402", "C403"]
    document["capacitors"][0]["quantity"] = 1
    issues = check(make_dataset(document))
    mismatch = [
        issue for issue in issues if issue.code == "quantity-designator-mismatch"
    ]
    assert len(mismatch) == 1
    assert mismatch[0].level == "error"


def test_no_designators_at_all_stays_legal() -> None:
    document = board_document()
    del document["capacitors"][0]["designators"]
    document["capacitors"][0]["quantity"] = 3
    assert "quantity-designator-mismatch" not in codes(make_dataset(document))


def test_a_designator_repeated_on_one_board_is_an_error() -> None:
    document = board_document()
    document["capacitors"][0]["designators"] = ["C20"]
    document["capacitors"].append(
        {
            "designators": ["C20"],
            "type": "electrolytic-radial",
            "capacitance_uf": 100,
            "voltage_v": 16,
            "quantity": 1,
        }
    )
    issues = check(make_dataset(document))
    duplicates = [issue for issue in issues if issue.code == "duplicate-designator"]
    assert len(duplicates) == 1
    assert duplicates[0].level == "error"
    assert "C20" in duplicates[0].message


def test_distinct_designators_are_fine() -> None:
    document = board_document()
    document["capacitors"].append(
        {
            "designators": ["C402"],
            "type": "electrolytic-radial",
            "capacitance_uf": 100,
            "voltage_v": 16,
            "quantity": 1,
        }
    )
    assert "duplicate-designator" not in codes(make_dataset(document))


def test_an_empty_capacitor_list_is_a_warning() -> None:
    document = board_document(capacitors=[])
    issues = check(make_dataset(document))
    empty = [issue for issue in issues if issue.code == "no-capacitors"]
    assert len(empty) == 1
    assert empty[0].level == "warning"


def test_only_the_first_verified_position_is_reported_once() -> None:
    document = board_document(verification="unverified")
    identical = {
        "designators": ["C401"],
        "type": "electrolytic-radial",
        "capacitance_uf": 3300,
        "voltage_v": 25,
        "quantity": 1,
        "verification": "verified",
    }
    document["capacitors"] = [dict(identical), dict(identical)]
    issues = [
        issue for issue in check(make_dataset(document))
        if issue.code == "verified-without-source"
    ]
    assert len(issues) == 1
    assert issues[0].location.endswith(":capacitors/0")


def test_a_machine_id_must_match_its_directory() -> None:
    machine = Machine.from_dict(
        {
            "id": "amiga-2000",
            "name": "Commodore Amiga 2000",
            "family": "amiga",
            "board_order": ["mainboard"],
        },
        path=Path("data/amiga-500/machine.yaml"),
    )
    dataset = Dataset(
        machines={"amiga-2000": machine},
        boards={},
        parts={},
        series={},
        suppliers={},
        offers={},
    )
    mismatches = [
        issue for issue in check(dataset) if issue.code == "id-path-mismatch"
    ]
    assert len(mismatches) == 1
    assert mismatches[0].level == "error"
    assert mismatches[0].location == "data/amiga-500/machine.yaml"


def test_a_machine_in_its_own_directory_is_fine() -> None:
    machine = Machine.from_dict(
        {
            "id": "amiga-500",
            "name": "Commodore Amiga 500",
            "family": "amiga",
            "board_order": ["mainboard"],
        },
        path=Path("data/amiga-500/machine.yaml"),
    )
    dataset = Dataset(
        machines={"amiga-500": machine},
        boards={},
        parts={},
        series={},
        suppliers={},
        offers={},
    )
    assert "id-path-mismatch" not in codes(dataset)


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
