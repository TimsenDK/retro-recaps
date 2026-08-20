"""The context builder — everything the site decides before a template runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.loader import load_dataset
from tools.model import Board, Dataset, Machine
from tools.site.context import (
    _release_sort_key,
    ANALOG_HAZARD,
    CRT_ANALOG_HAZARD,
    CRT_MACHINE_HAZARD,
    MACHINE_MAINS_HAZARD_ID,
    MAINS_HAZARD,
    Coverage,
    SiteContext,
    board_view,
    build_context,
    format_capacitance,
    format_voltage,
    hazards_for,
    machine_hazards,
    machine_mains_hazard,
    natural_key,
    note_view,
    reference_targets,
    verification_view,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    loaded, issues = load_dataset(FIXTURES / "site")
    assert issues == []
    return loaded


@pytest.fixture(scope="module")
def site(dataset: Dataset) -> SiteContext:
    return build_context(dataset)


def machine(site: SiteContext, machine_id: str):
    return next(m for m in site.machines if m.id == machine_id)


def board(site: SiteContext, board_id: str):
    return next(b for b in site.boards if b.id == board_id)


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def test_whole_values_lose_their_decimal_point() -> None:
    assert format_capacitance(3300.0) == "3300 µF"
    assert format_voltage(25.0) == "25 V"


def test_fractional_values_keep_their_digits() -> None:
    assert format_capacitance(3.9) == "3.9 µF"
    assert format_capacitance(0.47) == "0.47 µF"


def test_natural_key_orders_a500_before_a1000() -> None:
    names = ["Amiga 1000", "Amiga 500", "Amiga 2000"]
    assert sorted(names, key=natural_key) == [
        "Amiga 500",
        "Amiga 1000",
        "Amiga 2000",
    ]


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------


def test_only_verified_gets_the_verified_tone() -> None:
    assert verification_view("verified").tone == "verified"
    assert verification_view("derived").tone == "caution"
    assert verification_view("unverified").tone == "warning"


def test_derived_reads_as_a_caution_not_as_a_success() -> None:
    view = verification_view("derived")
    assert "confirmed" in view.headline
    assert "Count" in view.guidance


def test_an_unknown_status_is_not_quietly_treated_as_fine() -> None:
    view = verification_view("probably-ok")
    assert view.tone == "unknown"
    assert view.status == "probably-ok"


# --------------------------------------------------------------------------
# Coverage roll-up
# --------------------------------------------------------------------------


def test_machine_coverage_counts_its_boards(site: SiteContext) -> None:
    a500 = machine(site, "amiga-500")
    assert a500.coverage == Coverage(verified=1, unverified=1, empty=1)
    assert a500.coverage.total == 2


def test_one_unverified_board_unsettles_the_whole_machine(
    site: SiteContext,
) -> None:
    a500 = machine(site, "amiga-500")
    assert a500.coverage.worst == "unverified"
    assert a500.coverage.tone == "warning"
    assert a500.coverage.group_label == "Not established throughout"


def test_a_machine_of_derived_boards_says_so_without_claiming_verified(
    site: SiteContext,
) -> None:
    mac = machine(site, "mac-se")
    assert mac.coverage == Coverage(derived=2)
    assert mac.coverage.tone == "caution"
    assert mac.coverage.group_label == "All derived — none confirmed"


def test_coverage_summary_counts_boards_in_words() -> None:
    coverage = Coverage(verified=2, derived=1)
    assert coverage.summary == "3 boards — 2 verified, 1 derived"
    assert Coverage(verified=1).summary == "1 board — 1 verified"
    assert Coverage().summary == "No boards"


def test_all_verified_is_the_only_case_that_reads_as_settled() -> None:
    assert Coverage(verified=3).group_label == "All verified"
    assert Coverage(verified=3).tone == "verified"


def test_family_coverage_adds_up_its_machines(site: SiteContext) -> None:
    families = {family.id: family for family in site.families}
    assert families["amiga"].coverage == Coverage(verified=1, unverified=1, empty=1)
    assert families["macintosh"].coverage == Coverage(derived=2)


def test_families_come_in_the_declared_order(site: SiteContext) -> None:
    assert [family.id for family in site.families] == ["amiga", "macintosh"]


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def test_boards_follow_the_machines_recap_order_not_the_filenames(
    site: SiteContext,
) -> None:
    """`analog.yaml` sorts before `logic.yaml`; the recap order is the reverse."""
    mac = machine(site, "mac-se")
    assert [b.kind for b in mac.boards] == ["logic", "analog"]


def test_designators_sort_numerically_within_a_board(site: SiteContext) -> None:
    rows = board(site, "amiga-500-mainboard-rev6a").rows
    assert [row.designators for row in rows] == [("C8",), ("C321",), ()]


def test_a_position_without_designators_sorts_last(site: SiteContext) -> None:
    rows = board(site, "amiga-500-mainboard-rev6a").rows
    assert rows[-1].has_designators is False
    assert rows[-1].designator_label == "2 positions"


# --------------------------------------------------------------------------
# Board views
# --------------------------------------------------------------------------


def test_a_raised_voltage_shows_the_original_beside_it(site: SiteContext) -> None:
    row = next(
        r
        for r in board(site, "amiga-500-mainboard-rev6a").rows
        if r.designators == ("C321",)
    )
    assert row.voltage == "25 V"
    assert row.original_voltage_note == "was 16 V"


def test_an_unraised_voltage_says_nothing_about_the_original(
    site: SiteContext,
) -> None:
    row = next(
        r
        for r in board(site, "amiga-500-mainboard-rev6a").rows
        if r.designators == ("C8",)
    )
    assert row.original_voltage_note is None


def test_a_position_overriding_the_board_status_is_flagged(
    site: SiteContext,
) -> None:
    view = board(site, "amiga-500-mainboard-rev6a")
    assert view.verification.status == "verified"
    assert view.mixed_verification is True
    override = view.rows[-1]
    assert override.verification.status == "derived"
    assert override.differs_from_board is True


def test_board_counts_separate_positions_from_capacitors(
    site: SiteContext,
) -> None:
    view = board(site, "amiga-500-mainboard-rev6a")
    assert view.position_count == 3
    assert view.capacitor_count == 4


def test_boards_of_the_same_kind_are_told_apart_by_revision(
    site: SiteContext,
) -> None:
    """A machine with one board of a kind does not need the revision in the title."""
    assert board(site, "amiga-500-psu").title == "Power supply"


def test_board_urls_follow_the_data_layout(site: SiteContext) -> None:
    view = board(site, "amiga-500-mainboard-rev6a")
    assert view.url == "amiga-500/mainboard-rev6a.html"
    assert view.yaml_url == "amiga-500/mainboard-rev6a.yaml"
    assert view.json_url == "amiga-500/mainboard-rev6a.json"


# --------------------------------------------------------------------------
# The empty capacitor list
# --------------------------------------------------------------------------


def test_an_empty_list_is_an_open_question_not_an_empty_table(
    site: SiteContext,
) -> None:
    view = board(site, "amiga-500-psu")
    assert view.is_empty is True
    assert view.rows == ()
    assert view.open_question is not None
    assert "count" in view.open_question.lower()


def test_an_empty_list_keeps_the_notes_that_explain_it(site: SiteContext) -> None:
    view = board(site, "amiga-500-psu")
    assert view.notes
    assert "Count it before ordering" in view.notes[0]


def test_an_empty_board_is_counted_as_empty_in_the_roll_up(
    site: SiteContext,
) -> None:
    assert site.status.coverage.empty == 1
    assert [q.url for q in site.status.empty_boards] == ["amiga-500/psu.html"]


# --------------------------------------------------------------------------
# Hazards
# --------------------------------------------------------------------------


def test_a_psu_board_carries_the_mains_warning(site: SiteContext) -> None:
    assert MAINS_HAZARD in board(site, "amiga-500-psu").hazards


def test_a_crt_machines_analog_board_names_the_tube(site: SiteContext) -> None:
    hazards = board(site, "mac-se-analog").hazards
    assert CRT_ANALOG_HAZARD in hazards
    assert ANALOG_HAZARD not in hazards


def test_every_board_of_a_crt_machine_warns_about_the_tube(
    site: SiteContext,
) -> None:
    """The logic board is neither psu nor analog, and still sits by a CRT."""
    assert board(site, "mac-se-logic").hazards == (CRT_MACHINE_HAZARD,)


def test_a_mainboard_on_a_machine_without_a_crt_carries_no_warning(
    site: SiteContext,
) -> None:
    assert board(site, "amiga-500-mainboard-rev6a").hazards == ()


def test_a_machine_page_warns_when_it_holds_a_mains_board(
    site: SiteContext,
) -> None:
    ids = [hazard.id for hazard in machine(site, "amiga-500").hazards]
    assert ids == [MACHINE_MAINS_HAZARD_ID]
    assert [h.id for h in machine(site, "mac-se").hazards] == [
        MACHINE_MAINS_HAZARD_ID,
        CRT_MACHINE_HAZARD.id,
    ]


def test_a_machine_page_never_carries_the_board_page_wording(
    site: SiteContext,
) -> None:
    """'This board carries mains voltage' has no referent on a machine page."""
    for view in site.machines:
        assert MAINS_HAZARD not in view.hazards
        for hazard in view.hazards:
            assert "This board" not in hazard.body


# --------------------------------------------------------------------------
# Status page
# --------------------------------------------------------------------------


def test_status_lists_the_unverified_and_derived_boards_separately(
    site: SiteContext,
) -> None:
    status = site.status
    assert [q.url for q in status.unverified_boards] == ["amiga-500/psu.html"]
    assert {q.url for q in status.derived_boards} == {
        "mac-se/logic.html",
        "mac-se/analog.html",
    }


def test_status_finds_positions_without_designators(site: SiteContext) -> None:
    questions = site.status.positions_without_designators
    assert [q.url for q in questions] == ["amiga-500/mainboard-rev6a.html"]
    assert "1 position" in questions[0].detail


def test_status_total_is_every_open_question(site: SiteContext) -> None:
    status = site.status
    assert status.total == (
        len(status.empty_boards)
        + len(status.unverified_boards)
        + len(status.derived_boards)
        + len(status.positions_without_designators)
        + len(status.parts_without_offers)
    )


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def test_search_matches_a_designator(site: SiteContext) -> None:
    entry = next(e for e in site.search if e["url"] == "amiga-500/mainboard-rev6a.html")
    assert "c321" in entry["text"]
    assert "a500" in entry["text"]


def test_search_covers_every_machine_and_board(site: SiteContext) -> None:
    kinds = [entry["type"] for entry in site.search]
    assert kinds.count("machine") == len(site.machines)
    assert kinds.count("board") == len(site.boards)


# --------------------------------------------------------------------------
# The good fixture, which the rest of the suite also relies on
# --------------------------------------------------------------------------


def test_the_good_fixture_builds_a_coherent_context() -> None:
    loaded, issues = load_dataset(FIXTURES / "good")
    assert issues == []
    built = build_context(loaded)
    assert built.machine_count == 1
    assert built.board_count == 1
    assert built.capacitor_count == 3
    only = built.boards[0]
    assert only.verification.status == "verified"
    assert [row.designators for row in only.rows] == [("C321",), ("C401", "C402")]
    shielded = only.rows[1]
    assert shielded.part is not None
    assert shielded.part.mpn == "EEU-FR1E332"
    assert shielded.fit_limits == ("max height 24 mm",)


# --------------------------------------------------------------------------
# Hazards, decided by what the board declares it carries
# --------------------------------------------------------------------------


def hazard_board(kind: str, **overrides):
    document = {
        "id": "b",
        "machine": "m",
        "board": kind,
        "revisions": ["1"],
        "verification": "unverified",
        "capacitors": [],
    }
    return Board.from_dict({**document, **overrides})


def hazard_machine(family: str, **overrides) -> Machine:
    document = {
        "id": "m",
        "name": "A machine",
        "family": family,
        "released": "1987",
        "board_order": ["mainboard", "logic", "analog", "psu"],
    }
    return Machine.from_dict({**document, **overrides})


def test_a_crt_analog_board_that_carries_mains_gets_both_warnings() -> None:
    """Not one instead of the other.

    On an all-in-one Mac the analog board *is* the supply, so discharging the
    tube and then grabbing the board still leaves a charged bulk capacitor
    between the reader and the bench.
    """
    hazards = hazards_for(
        hazard_board("analog", mains=True), hazard_machine("macintosh")
    )
    assert hazards == (CRT_ANALOG_HAZARD, MAINS_HAZARD)


def test_a_crt_analog_board_declared_low_voltage_names_only_the_tube() -> None:
    hazards = hazards_for(
        hazard_board("analog", mains=False), hazard_machine("macintosh")
    )
    assert hazards == (CRT_ANALOG_HAZARD,)


def test_a_non_crt_analog_board_declared_low_voltage_gets_no_hazard() -> None:
    """The 1541-II analog board is low-voltage motor control, and says so."""
    hazards = hazards_for(
        hazard_board("analog", mains=False), hazard_machine("commodore-drive")
    )
    assert hazards == ()


def test_an_undeclared_analog_board_still_gets_the_hedging_warning() -> None:
    hazards = hazards_for(hazard_board("analog"), hazard_machine("commodore-drive"))
    assert hazards == (ANALOG_HAZARD,)


def test_a_mainboard_declared_mains_gets_the_mains_warning() -> None:
    """The 1541 longboard carries the machine's linear supply."""
    hazards = hazards_for(
        hazard_board("mainboard", mains=True), hazard_machine("commodore-drive")
    )
    assert hazards == (MAINS_HAZARD,)


def test_an_undeclared_mainboard_gets_no_warning() -> None:
    hazards = hazards_for(hazard_board("mainboard"), hazard_machine("amiga"))
    assert hazards == ()


def test_a_psu_declared_low_voltage_is_taken_at_its_word() -> None:
    hazards = hazards_for(hazard_board("psu", mains=False), hazard_machine("amiga"))
    assert hazards == ()


def test_an_undeclared_psu_still_warns() -> None:
    hazards = hazards_for(hazard_board("psu"), hazard_machine("amiga"))
    assert hazards == (MAINS_HAZARD,)


def test_a_mains_board_on_a_crt_machine_warns_about_both() -> None:
    hazards = hazards_for(
        hazard_board("psu", mains=True), hazard_machine("macintosh")
    )
    assert hazards == (MAINS_HAZARD, CRT_MACHINE_HAZARD)


def test_a_board_with_no_machine_still_reads_its_own_declaration() -> None:
    assert hazards_for(hazard_board("mainboard", mains=True), None) == (MAINS_HAZARD,)


def test_a_machine_whose_only_analog_board_is_low_voltage_has_no_mains() -> None:
    """The 1541-II machine page must not claim 'This is a power supply'."""
    machine = hazard_machine("commodore-drive")
    boards = [hazard_board("mainboard"), hazard_board("analog", mains=False)]
    assert machine_hazards(boards, machine) == ()


def test_a_machine_holding_mains_boards_raises_one_panel_naming_them() -> None:
    machine = hazard_machine("commodore-drive")
    boards = [
        hazard_board("mainboard", mains=True),
        hazard_board("analog", mains=False),
        hazard_board("psu", mains=True),
    ]
    hazards = machine_hazards(boards, machine)
    assert [hazard.id for hazard in hazards] == [MACHINE_MAINS_HAZARD_ID]
    body = hazards[0].body
    assert "mainboard" in body and "power supply" in body
    assert "analog" not in body


def test_the_machine_panel_names_a_lone_mains_board_in_the_singular() -> None:
    """The 1541-II's supply is a sealed external brick, not the drive."""
    hazard = machine_mains_hazard([hazard_board("psu", mains=True)])
    assert "This machine's power supply carries mains voltage." in hazard.body
    assert "Read the power supply page" in hazard.body


def test_the_machine_panel_sends_the_reader_to_the_board_pages() -> None:
    hazard = machine_mains_hazard(
        [hazard_board("psu", mains=True), hazard_board("analog", mains=True)]
    )
    assert "board pages" in hazard.body


def test_the_machine_panel_lists_each_board_kind_once() -> None:
    hazard = machine_mains_hazard(
        [hazard_board("psu", mains=True), hazard_board("psu", mains=True)]
    )
    assert hazard.body.count("power supply") == 2  # named once, followed once
    assert "This machine's power supply carries" in hazard.body


def test_a_crt_machine_warns_about_the_tube_with_no_mains_board() -> None:
    machine = hazard_machine("macintosh")
    assert machine_hazards([hazard_board("logic")], machine) == (CRT_MACHINE_HAZARD,)


# --------------------------------------------------------------------------
# The machine's battery, on the board page that gets printed
# --------------------------------------------------------------------------


def test_a_board_that_holds_the_cell_carries_the_battery(site: SiteContext) -> None:
    batteries = board(site, "amiga-500-mainboard-rev6a").batteries
    assert [b.kind for b in batteries] == ["nicd"]


def test_a_board_without_the_cell_stays_silent(dataset: Dataset) -> None:
    """The A500's battery is on rev 8A alone.

    Deciding this by board kind put the warning on rev 3, rev 5 and rev 6A
    too, hedged with a note telling the reader to go and check. A warning
    that cannot say whether it applies teaches the reader to skip warnings.
    """
    without = Board(
        id="amiga-500-mainboard-rev3",
        machine="amiga-500",
        board="mainboard",
        revisions=("3",),
        verification="derived",
        capacitors=(),
    )
    assert board_view(without, dataset, disambiguate=True).batteries == ()


def test_a_psu_page_does_not_claim_the_battery(site: SiteContext) -> None:
    assert board(site, "amiga-500-psu").batteries == ()


def test_a_logic_board_page_carries_the_battery_too(site: SiteContext) -> None:
    """Macintosh boards hold the cell; the site calls that kind 'logic'."""
    batteries = board(site, "mac-se-logic").batteries
    assert [b.kind for b in batteries] == ["pram"]


def test_an_analog_board_page_does_not_claim_the_battery(site: SiteContext) -> None:
    assert board(site, "mac-se-analog").batteries == ()


def test_the_machine_page_does_not_carry_the_battery(site: SiteContext) -> None:
    """The cell is on one revision, and only that board page may warn about it.

    A machine-level panel warns every owner of every revision, including the
    ones whose board has no cell — which is the warning the board pages were
    made precise to avoid.
    """
    assert not hasattr(machine(site, "amiga-500"), "batteries")


# --------------------------------------------------------------------------
# Cross-file references in notes
# --------------------------------------------------------------------------


def test_a_reference_to_a_sibling_board_becomes_a_link(dataset: Dataset) -> None:
    targets = reference_targets(dataset)
    note = "Shares a supply with amiga-500/psu.yaml on this machine."
    view = note_view(note, targets)
    assert [segment.url for segment in view.segments] == [
        None,
        "amiga-500/psu.html",
        None,
    ]
    assert view.has_links is True


def test_a_reference_is_replaced_by_the_page_it_names(dataset: Dataset) -> None:
    targets = reference_targets(dataset)
    view = note_view("See amiga-500/psu.yaml.", targets)
    link = next(segment for segment in view.segments if segment.is_link)
    assert link.text == "Commodore Amiga 500 — Power supply"


def test_a_reference_to_a_machine_file_links_to_the_machine_page(
    dataset: Dataset,
) -> None:
    targets = reference_targets(dataset)
    view = note_view("Also fitted to mac-se/machine.yaml.", targets)
    link = next(segment for segment in view.segments if segment.is_link)
    assert link.url == "mac-se/index.html"
    assert link.text == "Macintosh SE"


def test_a_reference_to_a_file_that_does_not_exist_stays_plain_text(
    dataset: Dataset,
) -> None:
    """A broken link on a printed sheet is worse than a searchable filename."""
    targets = reference_targets(dataset)
    view = note_view("See amiga-4000/mainboard.yaml.", targets)
    assert view.has_links is False
    assert view.text == "See amiga-4000/mainboard.yaml."


def test_a_bare_filename_is_not_a_reference(dataset: Dataset) -> None:
    """`psu.yaml` names nothing resolvable, which is why it is not the form."""
    view = note_view("See psu.yaml for the supply.", reference_targets(dataset))
    assert view.has_links is False


def test_a_relative_path_reference_is_not_resolved(dataset: Dataset) -> None:
    """`../amiga-500/psu.yaml` encodes the writer's position, not the target."""
    view = note_view("See ../amiga-500/psu.yaml.", reference_targets(dataset))
    assert view.has_links is False


def test_a_note_with_no_reference_is_one_plain_segment(dataset: Dataset) -> None:
    view = note_view("Two positions are unpopulated.", reference_targets(dataset))
    assert len(view.segments) == 1
    assert view.segments[0].is_link is False


def test_two_references_in_one_note_both_link(dataset: Dataset) -> None:
    targets = reference_targets(dataset)
    view = note_view(
        "Between amiga-500/psu.yaml and mac-se/logic.yaml.", targets
    )
    assert [segment.url for segment in view.segments if segment.is_link] == [
        "amiga-500/psu.html",
        "mac-se/logic.html",
    ]


def test_a_lone_board_of_its_kind_is_labelled_without_its_revision(
    dataset: Dataset,
) -> None:
    """The revision is only added where a machine has two boards of a kind."""
    targets = reference_targets(dataset)
    assert targets["amiga-500/mainboard-rev6a.yaml"][1] == (
        "Commodore Amiga 500 — Mainboard"
    )


def test_board_notes_arrive_at_the_template_already_split(site: SiteContext) -> None:
    view = board(site, "amiga-500-psu")
    assert len(view.linked_notes) == len(view.notes)
    assert view.linked_notes[0].text == view.notes[0]


def test_machine_notes_arrive_at_the_template_already_split(
    site: SiteContext,
) -> None:
    view = machine(site, "amiga-500")
    assert len(view.linked_notes) == len(view.notes)


def test_a_family_lists_its_machines_oldest_first() -> None:
    """A reader scanning a family is following the line as it was built.

    The order was alphabetical by name, which put the Amiga 1000 after the
    Amiga 500 and the 1541-II in the middle of the drives. `released` orders
    them instead, and it is required of every machine so the order cannot
    silently fall back to something else.
    """
    dataset, issues = load_dataset(Path(__file__).resolve().parent.parent)
    assert issues == []
    context = build_context(dataset)
    for family in context.families:
        keys = [_release_sort_key(machine) for machine in family.machines]
        assert keys == sorted(keys), family.id


def test_a_year_alone_sorts_after_a_month_in_the_same_year() -> None:
    """A bare year counts as the end of that year, not the start.

    Where one machine in a year is dated to a month and another only to the
    year, the vague one is almost always the variant that followed: the 128D
    against the 128, the Commodore 16 against the Plus/4. Treating the year as
    January put every such variant ahead of what it derives from.
    """
    early = hazard_machine("amiga", id="early", name="Early", released="1984-06")
    late = hazard_machine("amiga", id="late", name="Late", released="1984")
    dataset = Dataset(
        machines={m.id: m for m in (early, late)},
        boards={},
        parts={},
        series={},
        suppliers={},
        offers={},
    )
    context = build_context(dataset)
    assert [m.id for m in context.families[0].machines] == ["early", "late"]
