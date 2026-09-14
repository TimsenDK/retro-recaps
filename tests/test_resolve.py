from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tools.loader import load_dataset
from tools.model import Capacitor, Dataset, Part, Series
from tools.resolve import candidate_parts, matches, supplier_links
from tools.rules import check
from tools.stock import Stock, StockEntry

FIXTURES = Path(__file__).parent / "fixtures"


def load() -> object:
    dataset, issues = load_dataset(FIXTURES / "good")
    assert issues == []
    return dataset


def position(**overrides) -> Capacitor:
    base = {
        "designators": ["C401"],
        "type": "electrolytic-radial",
        "capacitance_uf": 3300,
        "voltage_v": 25,
        "quantity": 1,
    }
    return Capacitor.from_dict({**base, **overrides})


def test_a_pinned_part_wins_alone() -> None:
    dataset = load()
    parts = candidate_parts(position(part="eeufr1e332"), dataset)
    assert [part.id for part in parts] == ["eeufr1e332"]


def test_a_pinned_part_that_does_not_exist_yields_nothing() -> None:
    dataset = load()
    assert candidate_parts(position(part="ghost"), dataset) == []


def test_matching_finds_the_right_value() -> None:
    dataset = load()
    parts = candidate_parts(position(), dataset)
    assert [part.id for part in parts] == ["eeufr1e332"]


def test_matching_rejects_an_insufficient_voltage() -> None:
    dataset = load()
    assert candidate_parts(position(voltage_v=63), dataset) == []


def test_matching_rejects_the_wrong_type() -> None:
    dataset = load()
    assert candidate_parts(position(type="tantalum"), dataset) == []


def test_a_snap_in_part_is_not_offered_for_a_radial_position() -> None:
    """Different terminals, different pin count, different footprint."""
    dataset = load()
    snap_in = replace(
        dataset.parts["eeufr1e332"], id="snap", type="electrolytic-snap-in"
    )
    dataset = replace(dataset, parts={**dataset.parts, "snap": snap_in})
    assert "snap" not in {part.id for part in candidate_parts(position(), dataset)}


def test_a_radial_part_is_not_offered_for_a_snap_in_position() -> None:
    dataset = load()
    parts = candidate_parts(position(type="electrolytic-snap-in"), dataset)
    assert parts == []


def test_a_snap_in_part_is_offered_for_a_snap_in_position() -> None:
    dataset = load()
    snap_in = replace(
        dataset.parts["eeufr1e332"], id="snap", type="electrolytic-snap-in"
    )
    dataset = replace(dataset, parts={**dataset.parts, "snap": snap_in})
    parts = candidate_parts(position(type="electrolytic-snap-in"), dataset)
    assert [part.id for part in parts] == ["snap"]


def test_matching_rejects_a_part_that_is_too_tall() -> None:
    dataset = load()
    part = dataset.parts["eeufr1e332"]  # 20 mm tall
    assert not matches(part, position(max_height_mm=15))
    assert matches(part, position(max_height_mm=20))


def test_matching_rejects_a_part_that_is_too_wide() -> None:
    dataset = load()
    part = dataset.parts["eeufr1e332"]  # 12.5 mm diameter
    assert not matches(part, position(max_diameter_mm=10))
    assert matches(part, position(max_diameter_mm=12.5))


def test_matching_rejects_a_part_whose_leads_are_too_far_apart() -> None:
    dataset = load()
    part = dataset.parts["eeufr1e332"]  # 5 mm lead spacing
    assert not matches(part, position(max_lead_spacing_mm=3.5))
    assert matches(part, position(max_lead_spacing_mm=5))


def test_an_undeclared_dimension_never_rejects_a_part() -> None:
    """An incomplete catalogue must not silently drop every candidate."""
    dataset = load()
    unmeasured = replace(
        dataset.parts["eeufr1e332"],
        diameter_mm=None,
        height_mm=None,
        lead_spacing_mm=None,
    )
    assert matches(
        unmeasured,
        position(max_height_mm=1, max_diameter_mm=1, max_lead_spacing_mm=1),
    )


def test_an_over_height_part_is_not_offered_as_a_candidate() -> None:
    dataset = load()
    assert candidate_parts(position(max_height_mm=15), dataset) == []


def test_a_part_with_an_offer_gets_a_product_link() -> None:
    dataset = load()
    links = supplier_links(dataset.parts["eeufr1e332"], dataset)
    mouser = next(link for link in links if link.supplier_id == "mouser")
    assert mouser.kind == "product"
    assert mouser.url == "https://www.mouser.dk/ProductDetail/667-EEU-FR1E332"


def test_a_part_without_an_offer_falls_back_to_a_search_link() -> None:
    dataset = load()
    links = supplier_links(dataset.parts["eeufr1e470"], dataset)
    assert {link.kind for link in links} == {"search"}
    mouser = next(link for link in links if link.supplier_id == "mouser")
    assert mouser.url == "https://www.mouser.dk/c/?q=EEU-FR1E470"


def test_a_supplier_without_a_product_template_still_searches() -> None:
    dataset = load()
    links = supplier_links(dataset.parts["eeufr1e332"], dataset)
    digikey = next(link for link in links if link.supplier_id == "digikey")
    assert digikey.kind == "search"
    assert digikey.url.endswith("keywords=EEU-FR1E332")


def test_the_rules_and_the_resolver_agree_on_fit() -> None:
    """One definition of fit: check() and candidate_parts() cannot disagree."""
    dataset = load()
    board = dataset.boards["amiga-500-mainboard-rev6a"]
    for part in dataset.parts.values():
        for index, capacitor in enumerate(board.capacitors):
            pinned = replace(capacitor, part=part.id)
            candidate = replace(
                dataset,
                boards={board.id: replace(board, capacitors=(pinned,))},
            )
            rejected = any(
                issue.code in ("part-mismatch", "part-does-not-fit")
                for issue in check(candidate)
            )
            assert rejected != matches(part, pinned), (part.id, index)
            unpinned = replace(pinned, part=None)
            fits = part in candidate_parts(unpinned, dataset)
            assert fits != rejected, (part.id, index)


def test_mpn_is_url_quoted() -> None:
    dataset = load()
    part = dataset.parts["eeufr1e332"]
    quoted = part.__class__.from_dict(
        {
            "id": "spaced",
            "manufacturer": "Panasonic",
            "mpn": "EEU FR1E332",
            "series": "panasonic-fr",
            "type": "electrolytic-radial",
            "capacitance_uf": 3300,
            "voltage_v": 25,
        }
    )
    links = supplier_links(quoted, dataset)
    assert all("EEU%20FR1E332" in link.url for link in links)


# --------------------------------------------------------------------------
# Stock-aware selection
# --------------------------------------------------------------------------


def catalogue(*parts: Part) -> Dataset:
    """The good fixture's suppliers, with a hybrid series and these parts."""
    dataset = load()
    hybrid = Series(
        id="panasonic-zs",
        manufacturer="Panasonic",
        name="ZS",
        type="electrolytic-radial",
        hybrid=True,
    )
    other = Series(
        id="cde-std",
        manufacturer="Cornell Dubilier",
        name="STD",
        type="electrolytic-radial",
    )
    return replace(
        dataset,
        series={**dataset.series, hybrid.id: hybrid, other.id: other},
        parts={part.id: part for part in parts},
        offers={},
    )


def radial(part_id: str, **overrides) -> Part:
    base = {
        "id": part_id,
        "manufacturer": "Panasonic",
        "mpn": part_id.upper(),
        "series": "panasonic-fr",
        "type": "electrolytic-radial",
        "capacitance_uf": 3300,
        "voltage_v": 25,
        "height_mm": 20,
    }
    return Part.from_dict({**base, **overrides})


def stock(**levels: int | tuple[int, str]) -> Stock:
    """Stock by part id: a count, or (count, lifecycle)."""
    entries = {}
    for part_id, level in levels.items():
        count, lifecycle = level if isinstance(level, tuple) else (level, None)
        entries[part_id] = StockEntry(f"667-{part_id}", count, lifecycle)
    return Stock(fetched_at=None, parts=entries)


def ids(parts: list[Part]) -> list[str]:
    return [part.id for part in parts]


def test_an_in_stock_part_beats_a_hybrid_out_of_stock() -> None:
    dataset = catalogue(radial("plain"), radial("hyb", series="panasonic-zs"))
    chosen = candidate_parts(position(), dataset, stock(plain=10, hyb=0))
    assert ids(chosen) == ["plain", "hyb"]


def test_a_hybrid_beats_a_plain_part_when_both_are_in_stock() -> None:
    dataset = catalogue(radial("plain"), radial("hyb", series="panasonic-zs"))
    chosen = candidate_parts(position(), dataset, stock(plain=10, hyb=10))
    assert ids(chosen) == ["hyb", "plain"]


def test_a_position_that_forbids_hybrids_is_offered_none() -> None:
    dataset = catalogue(radial("plain"), radial("hyb", series="panasonic-zs"))
    chosen = candidate_parts(position(allow_hybrid=False), dataset)
    assert ids(chosen) == ["plain"]


def test_a_preferred_brand_beats_another_brand() -> None:
    dataset = catalogue(
        radial("cde", manufacturer="Cornell Dubilier", series="cde-std"),
        radial("pana"),
    )
    chosen = candidate_parts(position(), dataset, stock(cde=10, pana=10))
    assert ids(chosen) == ["pana", "cde"]


def test_unknown_stock_sorts_between_in_stock_and_out_of_stock() -> None:
    dataset = catalogue(radial("a-out"), radial("b-unknown"), radial("c-in"))
    levels = stock(**{"a-out": 0, "c-in": 5})
    assert ids(candidate_parts(position(), dataset, levels)) == [
        "c-in",
        "b-unknown",
        "a-out",
    ]


def test_without_a_stock_file_every_part_is_unknown_and_the_rest_decides() -> None:
    dataset = catalogue(radial("plain"), radial("hyb", series="panasonic-zs"))
    assert ids(candidate_parts(position(), dataset)) == ["hyb", "plain"]


def test_an_obsolete_part_is_not_offered() -> None:
    dataset = catalogue(radial("old"), radial("eol"), radial("new"))
    levels = stock(old=(900, "Obsolete"), eol=(900, "End of Life"), new=0)
    assert ids(candidate_parts(position(), dataset, levels)) == ["new"]


def test_the_position_series_breaks_a_tie_before_voltage_and_height() -> None:
    dataset = catalogue(
        radial("tall", height_mm=25),
        radial("short", height_mm=16),
        radial("higher", voltage_v=35, height_mm=10),
        radial("unmeasured", height_mm=None),
        radial("elsewhere", series="cde-std", height_mm=5),
    )
    chosen = candidate_parts(position(series="panasonic-fr"), dataset)
    assert ids(chosen) == ["short", "tall", "unmeasured", "higher", "elsewhere"]


def test_selection_still_enforces_the_fit_limits() -> None:
    dataset = catalogue(radial("tall", height_mm=25), radial("short", height_mm=16))
    chosen = candidate_parts(position(max_height_mm=20), dataset, stock(tall=99))
    assert ids(chosen) == ["short"]


def test_a_pinned_part_overrides_selection_whatever_its_stock() -> None:
    dataset = catalogue(radial("plain"), radial("hyb", series="panasonic-zs"))
    pinned = position(part="plain")
    chosen = candidate_parts(pinned, dataset, stock(plain=(0, "Obsolete"), hyb=9))
    assert ids(chosen) == ["plain"]


def test_the_stock_files_mouser_number_links_a_product_page() -> None:
    dataset = catalogue(radial("plain"))
    links = supplier_links(dataset.parts["plain"], dataset, stock(plain=3))
    mouser = next(link for link in links if link.supplier_id == "mouser")
    assert mouser.kind == "product"
    assert mouser.url == "https://www.mouser.dk/ProductDetail/667-plain"


def test_a_recorded_offer_wins_over_the_stock_file() -> None:
    dataset = load()
    part = dataset.parts["eeufr1e332"]
    links = supplier_links(part, dataset, stock(eeufr1e332=3))
    mouser = next(link for link in links if link.supplier_id == "mouser")
    assert mouser.url.endswith("/ProductDetail/667-EEU-FR1E332")
