from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from tools.loader import load_dataset
from tools.model import Capacitor
from tools.resolve import candidate_parts, matches, supplier_links
from tools.rules import check

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
