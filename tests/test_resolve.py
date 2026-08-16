from __future__ import annotations

from pathlib import Path

from tools.loader import load_dataset
from tools.model import Capacitor
from tools.resolve import candidate_parts, supplier_links

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
