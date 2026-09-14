"""Look every catalogued part up in the Mouser Search API.

Run by the `pages` workflow before every build, which holds the API key. It
writes the stock file the build selects parts from, keyed by part id, and
reports what Mouser lists for each MPN beside the stock number recorded in
`reference/offers/mouser.yaml`; it never edits the dataset.

    MOUSER_API_KEY=... python -m tools.mouser --root . --out stock.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from tools.loader import load_dataset
from tools.stock import parse_in_stock

ENDPOINT = "https://api.mouser.com/api/v1/search/partnumber?apiKey={key}"
BATCH = 10
"""The API takes at most ten pipe-separated part numbers per request."""


def search(mpns: list[str], key: str) -> dict:
    body = json.dumps(
        {
            "SearchByPartRequest": {
                "mouserPartNumber": "|".join(mpns),
                "partSearchOptions": "Exact",
            }
        }
    ).encode()
    request = urllib.request.Request(
        ENDPOINT.format(key=key),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def summarise(mpn: str, recorded: str | None, response: dict) -> dict:
    """One report entry: the listings whose manufacturer MPN is exactly `mpn`."""
    parts = (response.get("SearchResults") or {}).get("Parts") or []
    listings = [
        {
            "mouser_part_number": part.get("MouserPartNumber"),
            "manufacturer": part.get("Manufacturer"),
            "availability": part.get("Availability"),
            "in_stock": part.get("AvailabilityInStock"),
            "lifecycle": part.get("LifecycleStatus"),
            "url": part.get("ProductDetailUrl"),
        }
        for part in parts
        if (part.get("ManufacturerPartNumber") or "").upper() == mpn.upper()
    ]
    numbers = {listing["mouser_part_number"] for listing in listings}
    return {
        "mpn": mpn,
        "recorded": recorded,
        "recorded_matches": recorded in numbers if recorded else None,
        "listings": listings,
    }


def stock_entry(entry: dict) -> dict | None:
    """The one listing the build uses for a part, or None if Mouser has none.

    Where Mouser lists an MPN more than once (bulk and cut tape, say), the
    number already recorded in the offers file wins, since that is the listing
    the product link points at; otherwise the listing with most in stock.
    """
    listings = [
        listing for listing in entry["listings"] if listing["mouser_part_number"]
    ]
    if not listings:
        return None
    recorded = [
        listing
        for listing in listings
        if listing["mouser_part_number"] == entry["recorded"]
    ]
    if recorded:
        chosen = recorded[0]
    else:
        chosen = max(listings, key=lambda listing: parse_in_stock(listing["in_stock"]))
    return {
        "mouser_part_number": chosen["mouser_part_number"],
        "in_stock": parse_in_stock(chosen["in_stock"]),
        "lifecycle": chosen["lifecycle"],
        "url": chosen["url"],
    }


def stock_document(entries: dict[str, dict], fetched_at: str) -> dict:
    """The stock file: every part id Mouser lists, and nothing for the rest."""
    parts = {}
    for part_id in sorted(entries):
        chosen = stock_entry(entries[part_id])
        if chosen is not None:
            parts[part_id] = chosen
    return {"source": "mouser", "fetched_at": fetched_at, "parts": parts}


def markdown(report: list[dict]) -> str:
    lines = [
        "| MPN | Recorded | Mouser # | In stock | Lifecycle |",
        "|---|---|---|---|---|",
    ]
    for entry in report:
        listings = entry["listings"] or [{}]
        for listing in listings:
            lines.append(
                "| {mpn} | {recorded} | {number} | {stock} | {life} |".format(
                    mpn=entry["mpn"],
                    recorded=entry["recorded"] or "—",
                    number=listing.get("mouser_part_number") or "not listed",
                    stock=listing.get("in_stock") or "—",
                    life=listing.get("lifecycle") or "—",
                )
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("stock.json"))
    args = parser.parse_args(argv)

    key = os.environ.get("MOUSER_API_KEY")
    if not key:
        print("MOUSER_API_KEY is not set", file=sys.stderr)
        return 2

    dataset, _ = load_dataset(args.root)
    recorded = dataset.offers.get("mouser", {})
    parts = sorted(dataset.parts.values(), key=lambda part: part.mpn)

    by_part: dict[str, dict] = {}
    for start in range(0, len(parts), BATCH):
        batch = parts[start : start + BATCH]
        response = search([part.mpn for part in batch], key)
        if response.get("Errors"):
            print(json.dumps(response["Errors"]), file=sys.stderr)
            return 1
        for part in batch:
            by_part[part.id] = summarise(part.mpn, recorded.get(part.id), response)

    fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    args.out.write_text(
        json.dumps(stock_document(by_part, fetched_at), indent=2), encoding="utf-8"
    )
    report = [by_part[part.id] for part in parts]
    table = markdown(report)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Mouser lookup\n\n" + table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
