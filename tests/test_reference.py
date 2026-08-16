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
        assert series.temperature_c >= 105, series.id


def test_the_snap_in_series_is_typed_as_snap_in() -> None:
    """A snap-in can does not fit a radial-leaded footprint."""
    dataset, _ = load_dataset(ROOT)
    assert dataset.series["nichicon-lgn"].type == "electrolytic-snap-in"


def test_suppliers_can_all_build_a_search_link() -> None:
    dataset, _ = load_dataset(ROOT)
    assert set(dataset.suppliers) >= {"mouser", "digikey"}
    for supplier in dataset.suppliers.values():
        assert "{mpn}" in supplier.search_url
