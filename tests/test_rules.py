from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset
from tools.model import Board, Dataset, Layout, Machine, Part, Series, Supplier
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
            "released": "1987",
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
    document = board_document(capacitors=[], verification="derived")
    issues = check(make_dataset(document))
    empty = [issue for issue in issues if issue.code == "no-capacitors"]
    assert len(empty) == 1
    assert empty[0].level == "warning"


def test_an_unverified_stub_is_not_told_it_has_no_capacitors() -> None:
    """The schema licenses this shape; warning about it is arguing with it."""
    document = board_document(capacitors=[], verification="unverified")
    assert "no-capacitors" not in codes(make_dataset(document))


def test_a_machine_id_must_match_its_directory() -> None:
    machine = Machine.from_dict(
        {
            "id": "amiga-2000",
            "name": "Commodore Amiga 2000",
            "family": "amiga",
            "released": "1987",
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
            "released": "1987",
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
            "released": "1987",
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


# --------------------------------------------------------------------------
# Sourcing a replacement
# --------------------------------------------------------------------------


def test_a_position_naming_neither_a_series_nor_a_part_is_an_error() -> None:
    issues = check(make_dataset(board_document()))
    orphaned = [issue for issue in issues if issue.code == "no-series-or-part"]
    assert len(orphaned) == 1
    assert orphaned[0].level == "error"
    assert orphaned[0].location.endswith(":capacitors/0")


def test_a_position_naming_a_series_is_enough() -> None:
    series = Series.from_dict(series_document())
    document = board_document()
    document["capacitors"][0]["series"] = "panasonic-fr"
    dataset = make_dataset(document, series={"panasonic-fr": series})
    assert "no-series-or-part" not in codes(dataset)


def test_a_position_naming_only_a_part_is_enough() -> None:
    part = fitting_part()
    series = Series.from_dict(series_document())
    document = board_document()
    document["capacitors"][0]["part"] = part.id
    dataset = make_dataset(
        document, parts={part.id: part}, series={"panasonic-fr": series}
    )
    assert "no-series-or-part" not in codes(dataset)


# --------------------------------------------------------------------------
# A position may be less certain than its board, never more
# --------------------------------------------------------------------------


def test_a_position_claiming_more_than_its_board_is_an_error() -> None:
    document = board_document(
        verification="derived",
    )
    document["capacitors"][0]["verification"] = "verified"
    issues = check(make_dataset(document))
    over = [issue for issue in issues if issue.code == "position-over-verified"]
    assert len(over) == 1
    assert over[0].level == "error"
    assert over[0].location.endswith(":capacitors/0")


def test_a_position_less_certain_than_its_board_is_fine() -> None:
    document = board_document(
        verification="verified",
    )
    document["capacitors"][0]["verification"] = "derived"
    assert "position-over-verified" not in codes(make_dataset(document))


def test_a_position_matching_its_board_is_fine() -> None:
    document = board_document(
        verification="derived",
    )
    document["capacitors"][0]["verification"] = "derived"
    assert "position-over-verified" not in codes(make_dataset(document))


# --------------------------------------------------------------------------
# Two files claiming one revision
# --------------------------------------------------------------------------


def two_board_dataset(first: dict, second: dict) -> Dataset:
    machine = Machine.from_dict(
        {
            "id": "commodore-1541",
            "name": "Commodore 1541",
            "family": "commodore-drive",
            "released": "1982",
            "board_order": ["mainboard", "psu"],
        }
    )
    boards = {}
    for document, name in ((first, "long"), (second, "short")):
        board = Board.from_dict(
            document, path=Path(f"data/commodore-1541/mainboard-{name}.yaml")
        )
        boards[board.id] = board
    return Dataset(
        machines={machine.id: machine},
        boards=boards,
        parts={},
        series={},
        suppliers={},
        offers={},
    )


def drive_board(slug: str, revisions: list[str]) -> dict:
    return {
        "id": f"commodore-1541-mainboard-{slug}",
        "machine": "commodore-1541",
        "board": "mainboard",
        "revisions": revisions,
        "verification": "unverified",
        "capacitors": [],
    }


def test_two_files_claiming_one_revision_is_an_error() -> None:
    dataset = two_board_dataset(
        drive_board("long", ["1540050"]), drive_board("short", ["1540050"])
    )
    duplicates = [
        issue for issue in check(dataset) if issue.code == "duplicate-revision"
    ]
    assert len(duplicates) == 2
    assert {issue.level for issue in duplicates} == {"error"}
    assert {issue.location for issue in duplicates} == {
        "data/commodore-1541/mainboard-long.yaml",
        "data/commodore-1541/mainboard-short.yaml",
    }
    assert "1540050" in duplicates[0].message


def test_two_files_claiming_distinct_revisions_are_fine() -> None:
    dataset = two_board_dataset(
        drive_board("long", ["1540050"]), drive_board("short", ["250442"])
    )
    assert "duplicate-revision" not in codes(dataset)


def test_the_same_revision_on_two_board_kinds_is_not_a_duplicate() -> None:
    """Only one machine, one kind and one revision string collide."""
    second = drive_board("short", ["all known"])
    second["board"] = "psu"
    first = drive_board("long", ["all known"])
    assert "duplicate-revision" not in codes(two_board_dataset(first, second))


# --------------------------------------------------------------------------
# Mains and the X2 filter
# --------------------------------------------------------------------------


def mains_board(kind: str, **overrides) -> dict:
    return board_document(
        board=kind,
        **overrides,
    )


def mains_dataset(document: dict) -> Dataset:
    machine = Machine.from_dict(
        {
            "id": "amiga-500",
            "name": "Commodore Amiga 500",
            "family": "amiga",
            "released": "1987",
            "board_order": ["mainboard", "psu", "analog"],
        }
    )
    board = Board.from_dict(document, path=Path("data/amiga-500/mainboard-rev6a.yaml"))
    return Dataset(
        machines={machine.id: machine},
        boards={board.id: board},
        parts={},
        series={},
        suppliers={},
        offers={},
    )


def test_a_psu_must_declare_mains_either_way() -> None:
    issues = check(mains_dataset(mains_board("psu")))
    undeclared = [issue for issue in issues if issue.code == "mains-not-declared"]
    assert len(undeclared) == 1
    assert undeclared[0].level == "error"


def test_an_analog_board_must_declare_mains_either_way() -> None:
    issues = check(mains_dataset(mains_board("analog")))
    assert any(
        issue.code == "mains-not-declared" and issue.level == "error"
        for issue in issues
    )


def test_declaring_mains_false_satisfies_the_rule() -> None:
    """The 1541-II analog board is low-voltage motor control, and says so."""
    assert "mains-not-declared" not in codes(
        mains_dataset(mains_board("analog", mains=False))
    )


def test_a_mainboard_need_not_declare_mains() -> None:
    assert "mains-not-declared" not in codes(mains_dataset(mains_board("mainboard")))


def test_a_mains_carrying_board_should_declare_its_x2_filter() -> None:
    issues = check(mains_dataset(mains_board("psu", mains=True)))
    undeclared = [issue for issue in issues if issue.code == "x2-filter-not-declared"]
    assert len(undeclared) == 1
    assert undeclared[0].level == "warning"


def test_a_mainboard_declared_mains_also_wants_an_x2_declaration() -> None:
    """The 1541 longboard carries the machine's linear supply."""
    assert "x2-filter-not-declared" in codes(
        mains_dataset(mains_board("mainboard", mains=True))
    )


def test_a_declared_x2_filter_raises_no_warning() -> None:
    document = mains_board("psu", mains=True, x2_filter="unknown")
    assert "x2-filter-not-declared" not in codes(mains_dataset(document))


def test_a_low_voltage_board_is_not_asked_about_an_x2_filter() -> None:
    document = mains_board("analog", mains=False)
    assert "x2-filter-not-declared" not in codes(mains_dataset(document))


def test_x2_filter_listed_without_a_film_x2_position_is_an_error() -> None:
    document = mains_board("psu", mains=True, x2_filter="listed")
    issues = check(mains_dataset(document))
    absent = [issue for issue in issues if issue.code == "x2-filter-listed-but-absent"]
    assert len(absent) == 1
    assert absent[0].level == "error"


def test_x2_filter_listed_alongside_a_film_x2_position_is_fine() -> None:
    document = mains_board("psu", mains=True, x2_filter="listed")
    document["capacitors"] = [
        {
            "designators": ["C1"],
            "type": "film-x2",
            "capacitance_uf": 0.1,
            "voltage_v": 275,
            "quantity": 1,
        }
    ]
    assert "x2-filter-listed-but-absent" not in codes(mains_dataset(document))


def test_x2_filter_absent_needs_no_film_x2_position() -> None:
    document = mains_board("psu", mains=True, x2_filter="absent")
    assert "x2-filter-listed-but-absent" not in codes(mains_dataset(document))


def test_an_x2_filter_on_a_board_that_is_not_mains_is_an_error() -> None:
    document = mains_board("analog", mains=False, x2_filter="absent")
    issues = check(mains_dataset(document))
    off = [issue for issue in issues if issue.code == "x2-filter-off-mains"]
    assert len(off) == 1
    assert off[0].level == "error"


def test_an_x2_filter_on_an_undeclared_mainboard_is_an_error() -> None:
    """An undeclared mainboard is not-mains, so it has no input filter."""
    document = mains_board("mainboard", x2_filter="unknown")
    assert "x2-filter-off-mains" in codes(mains_dataset(document))


# --------------------------------------------------------------------------
# The two 'the record is silent' markers
# --------------------------------------------------------------------------


def test_declaring_designators_unknown_suppresses_the_warning() -> None:
    document = board_document()
    del document["capacitors"][0]["designators"]
    document["capacitors"][0]["designators_unknown"] = True
    assert "no-designators" not in codes(make_dataset(document))


def test_declaring_original_voltage_unknown_suppresses_the_warning() -> None:
    document = board_document()
    document["capacitors"][0]["original_voltage_unknown"] = True
    assert "no-original-voltage" not in codes(make_dataset(document))


def test_the_markers_do_not_suppress_each_other() -> None:
    document = board_document()
    del document["capacitors"][0]["designators"]
    document["capacitors"][0]["designators_unknown"] = True
    assert "no-original-voltage" in codes(make_dataset(document))


# --------------------------------------------------------------------------
# A series only covers the voltages it is made in
# --------------------------------------------------------------------------


def ranged_series(**overrides) -> Series:
    return Series.from_dict(
        series_document(voltage_min_v=6.3, voltage_max_v=100, **overrides)
    )


def position_at(voltage_v: float, series_id: str = "panasonic-fr") -> dict:
    document = board_document()
    document["capacitors"][0]["series"] = series_id
    document["capacitors"][0]["voltage_v"] = voltage_v
    return document


def test_a_position_above_its_series_range_is_an_error() -> None:
    """The Macintosh 160-250 V positions pointed at a 6.3-100 V series."""
    dataset = make_dataset(
        position_at(250), series={"panasonic-fr": ranged_series()}
    )
    issues = [
        issue
        for issue in check(dataset)
        if issue.code == "series-voltage-out-of-range"
    ]
    assert len(issues) == 1
    assert issues[0].level == "error"
    assert "250" in issues[0].message
    assert "100" in issues[0].message


def test_a_position_below_its_series_range_is_an_error() -> None:
    dataset = make_dataset(
        position_at(4), series={"panasonic-fr": ranged_series()}
    )
    assert "series-voltage-out-of-range" in codes(dataset)


def test_a_position_inside_its_series_range_is_fine() -> None:
    dataset = make_dataset(
        position_at(25), series={"panasonic-fr": ranged_series()}
    )
    assert "series-voltage-out-of-range" not in codes(dataset)


def test_the_ends_of_the_range_are_inclusive() -> None:
    series = {"panasonic-fr": ranged_series()}
    for voltage in (6.3, 100):
        assert "series-voltage-out-of-range" not in codes(
            make_dataset(position_at(voltage), series=series)
        )


def test_a_series_with_no_range_recorded_constrains_nothing() -> None:
    """Silence means nobody has read the datasheet, not that it is unbounded."""
    series = Series.from_dict(series_document())
    dataset = make_dataset(position_at(450), series={"panasonic-fr": series})
    assert "series-voltage-out-of-range" not in codes(dataset)


def test_a_half_open_range_still_constrains_the_end_it_states() -> None:
    series = Series.from_dict(series_document(voltage_max_v=100))
    assert "series-voltage-out-of-range" in codes(
        make_dataset(position_at(160), series={"panasonic-fr": series})
    )
    assert "series-voltage-out-of-range" not in codes(
        make_dataset(position_at(4), series={"panasonic-fr": series})
    )


def test_the_wrong_series_type_is_reported_instead_of_the_range() -> None:
    """One fault per position; 'wrong family' makes the range beside the point."""
    series = Series.from_dict(
        series_document(id="nichicon-ues", name="UES", type="bipolar",
                        voltage_min_v=6.3, voltage_max_v=100)
    )
    dataset = make_dataset(
        position_at(250, "nichicon-ues"), series={"nichicon-ues": series}
    )
    assert "series-type-mismatch" in codes(dataset)
    assert "series-voltage-out-of-range" not in codes(dataset)


def test_a_catalogue_part_outside_its_series_range_is_an_error() -> None:
    part = Part.from_dict(
        {
            "id": "toohigh",
            "manufacturer": "Panasonic",
            "mpn": "X",
            "series": "panasonic-fr",
            "type": "electrolytic-radial",
            "capacitance_uf": 47,
            "voltage_v": 250,
        }
    )
    dataset = make_dataset(
        board_document(),
        parts={"toohigh": part},
        series={"panasonic-fr": ranged_series()},
    )
    issues = [
        issue
        for issue in check(dataset)
        if issue.code == "series-voltage-out-of-range"
    ]
    assert len(issues) == 1
    assert issues[0].location == "reference/parts.yaml:toohigh"


def test_x2_filter_listed_is_satisfied_by_a_y_class_position() -> None:
    """The Macintosh supplies filter with Y-class parts, not X2."""
    document = mains_board("psu", mains=True, x2_filter="listed")
    document["capacitors"] = [
        {
            "designators": ["C1"],
            "type": "film-y2",
            "capacitance_uf": 0.0047,
            "voltage_v": 250,
            "quantity": 1,
        }
    ]
    assert "x2-filter-listed-but-absent" not in codes(mains_dataset(document))


def y2_position(voltage_v: float) -> dict:
    document = board_document()
    document["capacitors"][0].update(
        {"type": "film-y2", "capacitance_uf": 0.0047, "voltage_v": voltage_v}
    )
    return document


def test_a_film_y2_below_250v_is_an_error() -> None:
    issues = check(make_dataset(y2_position(110)))
    too_low = [issue for issue in issues if issue.code == "y2-voltage-too-low"]
    assert len(too_low) == 1
    assert too_low[0].level == "error"
    assert "250" in too_low[0].message


def test_a_film_y2_at_250v_is_fine() -> None:
    assert "y2-voltage-too-low" not in codes(make_dataset(y2_position(250)))


def test_a_film_y2_at_300v_is_fine() -> None:
    assert "y2-voltage-too-low" not in codes(make_dataset(y2_position(300)))


def test_the_x2_floor_does_not_fire_on_a_y2_position() -> None:
    """250 VAC is a legal Y2 rating and below the 275 VAC X2 floor."""
    assert "x2-voltage-too-low" not in codes(make_dataset(y2_position(250)))


def test_the_y2_floor_does_not_fire_on_an_x2_position() -> None:
    document = board_document()
    document["capacitors"][0].update(
        {"type": "film-x2", "capacitance_uf": 0.1, "voltage_v": 275}
    )
    assert "y2-voltage-too-low" not in codes(make_dataset(document))


def demo_machine() -> Machine:
    return Machine.from_dict(
        {
            "id": "demo",
            "name": "Demo Machine",
            "family": "demo",
            "released": "1987",
            "board_order": ["mainboard"],
        }
    )


def demo_board(designators: list[str], **overrides: object) -> Board:
    document = {
        "id": "demo-mainboard",
        "machine": "demo",
        "board": "mainboard",
        "revisions": ["A"],
        "verification": "unverified",
        "capacitors": [
            {
                "designators": designators,
                "type": "electrolytic-radial",
                "capacitance_uf": 100,
                "voltage_v": 16,
                "quantity": len(designators),
            }
        ],
    }
    document.update(overrides)
    return Board.from_dict(document, path=Path("data/demo/mainboard.yaml"))


def layout_document(features: list[dict], **overrides: object) -> dict:
    document = {
        "id": "demo-layout-mainboard",
        "board": "demo-mainboard",
        "precision": "measured",
        "verification": "derived",
        "orientation": "Component side up.",
        "outline": {"width": 1000, "height": 620},
        "features": features,
    }
    document.update(overrides)
    return document


def dataset_with_layout(
    board_designators: list[str],
    features: list[dict],
    board_ref: str | None = None,
    precision: str = "measured",
    verification: str = "derived",
) -> Dataset:
    machine = demo_machine()
    board = demo_board(board_designators)
    layout = Layout.from_dict(
        layout_document(
            features,
            board=board_ref or board.id,
            precision=precision,
            verification=verification,
        ),
        path=Path("data/demo/layout-mainboard.yaml"),
    )
    return Dataset(
        machines={machine.id: machine},
        boards={board.id: board},
        parts={},
        series={},
        suppliers={},
        offers={},
        layouts={layout.id: layout},
    )


def dataset_with_unmappable_board() -> Dataset:
    """A board whose one position never named its designators.

    A layout cannot legitimately place a designator that does not appear
    anywhere on the board, so this board can never be fully mapped.
    """
    machine = demo_machine()
    board = demo_board(
        [],
        capacitors=[
            {
                "designators_unknown": True,
                "type": "electrolytic-radial",
                "capacitance_uf": 100,
                "voltage_v": 16,
                "quantity": 1,
            }
        ],
    )
    layout = Layout.from_dict(
        layout_document([], board=board.id),
        path=Path("data/demo/layout-mainboard.yaml"),
    )
    return Dataset(
        machines={machine.id: machine},
        boards={board.id: board},
        parts={},
        series={},
        suppliers={},
        offers={},
        layouts={layout.id: layout},
    )


def test_a_layout_may_not_place_a_designator_the_board_does_not_list() -> None:
    dataset = dataset_with_layout(
        board_designators=["C1"],
        features=[
            {"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1},
            {"kind": "capacitor", "designator": "C9", "x": 0.2, "y": 0.2},
        ],
    )
    assert "layout-designator-not-on-board" in codes(dataset)


def test_a_layout_may_not_leave_out_a_designator_the_board_lists() -> None:
    dataset = dataset_with_layout(
        board_designators=["C1", "C2"],
        features=[{"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1}],
    )
    issues = [i for i in check(dataset) if i.code == "layout-designator-missing"]
    assert issues and issues[0].level == "error"
    assert "C2" in issues[0].message


def test_a_complete_layout_raises_nothing() -> None:
    dataset = dataset_with_layout(
        board_designators=["C1", "C2"],
        features=[
            {"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1},
            {"kind": "capacitor", "designator": "C2", "x": 0.2, "y": 0.2},
            {"kind": "anchor", "label": "Power connector", "x": 0.9, "y": 0.5},
        ],
    )
    assert [i for i in check(dataset) if i.code.startswith("layout-")] == []


def test_a_layout_for_an_unknown_board_is_an_error() -> None:
    dataset = dataset_with_layout(
        board_designators=["C1"],
        features=[{"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1}],
        board_ref="demo-nonexistent",
    )
    assert "layout-unknown-board" in codes(dataset)


def test_a_board_with_unnamed_designators_cannot_be_mapped() -> None:
    dataset = dataset_with_unmappable_board()
    assert "layout-unmappable-board" in codes(dataset)


def test_an_approximate_layout_may_not_claim_to_be_verified() -> None:
    dataset = dataset_with_layout(
        board_designators=["C1"],
        features=[{"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1}],
        precision="approximate",
        verification="verified",
    )
    issues = [i for i in check(dataset) if i.code == "layout-approximate-but-verified"]
    assert issues and issues[0].level == "warning"


def test_a_designator_placed_twice_in_one_layout_is_an_error() -> None:
    # Layout.designators is a frozenset, so this pair would otherwise pass
    # the set-equality checks above cleanly: the board wants C1, the map
    # "has" C1. Only counting the features catches that two of them do.
    dataset = dataset_with_layout(
        board_designators=["C1"],
        features=[
            {"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1},
            {"kind": "capacitor", "designator": "C1", "x": 0.8, "y": 0.8},
        ],
    )
    issues = [i for i in check(dataset) if i.code == "layout-duplicate-designator"]
    assert issues and issues[0].level == "error"
    assert "C1" in issues[0].message


def test_two_layouts_claiming_the_same_board_is_an_error() -> None:
    machine = demo_machine()
    board = demo_board(["C1"])
    first = Layout.from_dict(
        layout_document(
            [{"kind": "capacitor", "designator": "C1", "x": 0.1, "y": 0.1}],
            id="demo-layout-mainboard",
            board=board.id,
        ),
        path=Path("data/demo/layout-mainboard.yaml"),
    )
    second = Layout.from_dict(
        layout_document(
            [{"kind": "capacitor", "designator": "C1", "x": 0.2, "y": 0.2}],
            id="demo-layout-mainboard-old",
            board=board.id,
        ),
        path=Path("data/demo/layout-mainboard-old.yaml"),
    )
    dataset = Dataset(
        machines={machine.id: machine},
        boards={board.id: board},
        parts={},
        series={},
        suppliers={},
        offers={},
        layouts={first.id: first, second.id: second},
    )
    issues = [i for i in check(dataset) if i.code == "layout-duplicate-board"]
    assert len(issues) == 2
    assert all(issue.level == "error" for issue in issues)
    locations = {issue.location for issue in issues}
    assert locations == {
        "data/demo/layout-mainboard.yaml",
        "data/demo/layout-mainboard-old.yaml",
    }
    assert "demo-layout-mainboard-old" in issues[0].message or (
        "demo-layout-mainboard-old" in issues[1].message
    )
