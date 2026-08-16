"""The context builder — everything the site decides before a template runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.loader import load_dataset
from tools.model import Dataset
from tools.site.context import (
    ANALOG_HAZARD,
    CRT_ANALOG_HAZARD,
    CRT_MACHINE_HAZARD,
    MAINS_HAZARD,
    Coverage,
    SiteContext,
    build_context,
    format_capacitance,
    format_voltage,
    natural_key,
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
    assert MAINS_HAZARD in machine(site, "amiga-500").hazards
    assert machine(site, "mac-se").hazards == (MAINS_HAZARD, CRT_MACHINE_HAZARD)


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


def test_status_finds_boards_without_sources(site: SiteContext) -> None:
    urls = {q.url for q in site.status.boards_without_sources}
    assert "amiga-500/mainboard-rev6a.html" not in urls
    assert "amiga-500/psu.html" in urls


def test_status_total_is_every_open_question(site: SiteContext) -> None:
    status = site.status
    assert status.total == (
        len(status.empty_boards)
        + len(status.unverified_boards)
        + len(status.derived_boards)
        + len(status.boards_without_sources)
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
