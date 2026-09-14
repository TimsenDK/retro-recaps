from __future__ import annotations

import json
from pathlib import Path

from tools.mouser import markdown, stock_document, summarise
from tools.stock import is_end_of_life, load_stock, parse_in_stock

RESPONSE = {
    "Errors": [],
    "SearchResults": {
        "Parts": [
            {
                "ManufacturerPartNumber": "EEU-FR1E471",
                "MouserPartNumber": "667-EEU-FR1E471",
                "Manufacturer": "Panasonic",
                "AvailabilityInStock": "1200",
                "LifecycleStatus": None,
                "ProductDetailUrl": "https://www.mouser.dk/ProductDetail/667-EEU-FR1E471",
            },
            {
                "ManufacturerPartNumber": "EEU-FR1E471B",
                "MouserPartNumber": "667-EEU-FR1E471B",
            },
        ]
    },
}


def test_only_the_exact_mpn_is_reported_and_checked_against_the_record() -> None:
    entry = summarise("EEU-FR1E471", "667-EEU-FR1E471", RESPONSE)
    assert [listing["mouser_part_number"] for listing in entry["listings"]] == [
        "667-EEU-FR1E471"
    ]
    assert entry["recorded_matches"] is True


def test_a_part_mouser_does_not_list_says_so() -> None:
    entry = summarise("EEU-FR1H4R7", None, RESPONSE)
    assert entry["listings"] == []
    assert entry["recorded_matches"] is None
    assert "not listed" in markdown([entry])


def test_the_stock_file_is_keyed_by_part_id_and_parses_the_count() -> None:
    entries = {
        "eeufr1e471": summarise("EEU-FR1E471", None, RESPONSE),
        "eeufr1h4r7": summarise("EEU-FR1H4R7", None, RESPONSE),
    }
    document = stock_document(entries, "2026-09-14T09:00:00Z")
    assert document["source"] == "mouser"
    assert document["fetched_at"] == "2026-09-14T09:00:00Z"
    assert document["parts"] == {
        "eeufr1e471": {
            "mouser_part_number": "667-EEU-FR1E471",
            "in_stock": 1200,
            "lifecycle": None,
            "url": "https://www.mouser.dk/ProductDetail/667-EEU-FR1E471",
        }
    }


def test_the_recorded_listing_wins_over_a_better_stocked_one() -> None:
    response = {
        "SearchResults": {
            "Parts": [
                {
                    "ManufacturerPartNumber": "UHE1E102MPD",
                    "MouserPartNumber": "647-UHE1E102MPD",
                    "AvailabilityInStock": "40",
                },
                {
                    "ManufacturerPartNumber": "UHE1E102MPD",
                    "MouserPartNumber": "647-UHE1E102MPD1TD",
                    "AvailabilityInStock": "9000",
                },
            ]
        }
    }
    unrecorded = summarise("UHE1E102MPD", None, response)
    recorded = summarise("UHE1E102MPD", "647-UHE1E102MPD", response)
    parts = stock_document({"a": unrecorded, "b": recorded}, "t")["parts"]
    assert parts["a"]["mouser_part_number"] == "647-UHE1E102MPD1TD"
    assert parts["b"]["mouser_part_number"] == "647-UHE1E102MPD"
    assert parts["b"]["in_stock"] == 40


def test_a_listing_without_a_stock_figure_counts_as_none_in_stock() -> None:
    response = {
        "SearchResults": {
            "Parts": [
                {
                    "ManufacturerPartNumber": "EEU-FR1E471",
                    "MouserPartNumber": "667-EEU-FR1E471",
                    "AvailabilityInStock": None,
                    "LifecycleStatus": "Obsolete",
                }
            ]
        }
    }
    entry = summarise("EEU-FR1E471", None, response)
    part = stock_document({"p": entry}, "t")["parts"]["p"]
    assert part["in_stock"] == 0
    assert part["lifecycle"] == "Obsolete"


def test_availability_strings_become_counts() -> None:
    assert parse_in_stock("8387") == 8387
    assert parse_in_stock(None) == 0
    assert parse_in_stock("") == 0
    assert parse_in_stock("On Order") == 0
    assert parse_in_stock(12) == 12


def test_only_an_obsolete_or_end_of_life_status_counts_as_gone() -> None:
    assert is_end_of_life("Obsolete")
    assert is_end_of_life("End of Life")
    assert not is_end_of_life("New Product")
    assert not is_end_of_life("Not Recommended for New Designs")
    assert not is_end_of_life(None)


def test_a_missing_or_broken_stock_file_is_no_stock(tmp_path: Path) -> None:
    assert load_stock(tmp_path / "absent.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert load_stock(broken) is None


def test_a_stock_file_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "stock.json"
    entries = {"eeufr1e471": summarise("EEU-FR1E471", None, RESPONSE)}
    path.write_text(json.dumps(stock_document(entries, "t")), encoding="utf-8")
    loaded = load_stock(path)
    assert loaded is not None
    entry = loaded.get("eeufr1e471")
    assert entry is not None
    assert entry.in_stock == 1200
    assert not entry.end_of_life
