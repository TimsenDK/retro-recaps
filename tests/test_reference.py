from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset
from tools.rules import check

ROOT = Path(__file__).resolve().parents[1]


def test_the_repository_reference_data_loads_and_validates() -> None:
    dataset, issues = load_dataset(ROOT)
    assert [issue for issue in issues if issue.level == "error"] == []
    errors = [issue for issue in check(dataset) if issue.level == "error"]
    assert errors == []


def test_the_series_the_project_standardised_on_are_present() -> None:
    dataset, _ = load_dataset(ROOT)
    expected = {
        "panasonic-fr",
        "panasonic-fk",
        "nichicon-upw",
        "nichicon-ues",
        "nichicon-lgn",
        "kemet-r46",
        "tdk-b32922",
        "vishay-021-asm",
        "kemet-t491",
    }
    assert expected <= set(dataset.series)


BELOW_105C = {
    # Nichicon's own page rates UES at 85 °C, and Vishay's datasheet gives the
    # 021 ASM an 85 °C category temperature. No 105 °C leaded-axial or bipolar
    # equivalent has been established, so these two positions sit at the
    # original temperature class rather than being mislabelled as 105 °C.
    "nichicon-ues": 85,
    "vishay-021-asm": 85,
}


def test_every_series_is_rated_at_least_105c_where_it_applies() -> None:
    dataset, _ = load_dataset(ROOT)
    applicable = [
        series
        for series in dataset.series.values()
        if series.type.startswith("electrolytic") or series.type == "bipolar"
    ]
    assert applicable
    # Snap-in is an electrolytic type, so retyping nichicon-lgn must not have
    # quietly moved it outside this rule.
    assert "nichicon-lgn" in {series.id for series in applicable}
    for series in applicable:
        assert series.temperature_c is not None, series.id
        if series.id in BELOW_105C:
            continue
        assert series.temperature_c >= 105, series.id


def test_the_two_sub_105c_series_are_labelled_honestly() -> None:
    """They may not drift back to a 105 °C label without a source for it."""
    dataset, _ = load_dataset(ROOT)
    for series_id, temperature in BELOW_105C.items():
        series = dataset.series[series_id]
        assert series.temperature_c == temperature, series_id
        assert series.note is not None and "85 °C" in series.note, series_id


def test_the_high_voltage_radial_series_reaches_the_crt_side_positions() -> None:
    """Panasonic FR stops at 100 V; the 160-400 V positions need this one."""
    dataset, _ = load_dataset(ROOT)
    series = dataset.series["nichicon-ucy"]
    assert series.type == "electrolytic-radial"
    assert series.temperature_c >= 105
    for voltage in (160, 200, 250, 350, 400, 450):
        assert series.covers(voltage), voltage


def test_the_default_radial_series_does_not_claim_the_high_voltages() -> None:
    dataset, _ = load_dataset(ROOT)
    series = dataset.series["panasonic-fr"]
    assert series.covers(100) is True
    assert series.covers(160) is False


def test_a_y_class_film_series_exists_for_the_isolation_barrier() -> None:
    dataset, _ = load_dataset(ROOT)
    y2 = [series for series in dataset.series.values() if series.type == "film-y2"]
    assert y2, "no Y-class series is recorded"


def test_the_mains_film_series_record_no_voltage_range() -> None:
    """A safety-film datasheet states one rating, not a manufacturing span."""
    dataset, _ = load_dataset(ROOT)
    for series in dataset.series.values():
        if not series.type.startswith("film"):
            continue
        assert series.voltage_range is None, series.id


def test_every_electrolytic_series_records_the_voltages_it_is_made_in() -> None:
    dataset, _ = load_dataset(ROOT)
    for series in dataset.series.values():
        if not (
            series.type.startswith("electrolytic") or series.type == "bipolar"
        ):
            continue
        assert series.voltage_min_v is not None, series.id
        assert series.voltage_max_v is not None, series.id
        assert series.voltage_min_v < series.voltage_max_v, series.id


def test_the_snap_in_series_is_typed_as_snap_in() -> None:
    """A snap-in can does not fit a radial-leaded footprint."""
    dataset, _ = load_dataset(ROOT)
    assert dataset.series["nichicon-lgn"].type == "electrolytic-snap-in"


def test_suppliers_can_all_build_a_search_link() -> None:
    dataset, _ = load_dataset(ROOT)
    assert set(dataset.suppliers) >= {"mouser", "digikey"}
    for supplier in dataset.suppliers.values():
        assert "{mpn}" in supplier.search_url
