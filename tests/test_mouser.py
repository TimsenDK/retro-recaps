from __future__ import annotations

from tools.mouser import markdown, summarise

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
