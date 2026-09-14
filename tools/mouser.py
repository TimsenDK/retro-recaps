"""Look every catalogued part up in the Mouser Search API.

Run by the `mouser` workflow, which holds the API key. It reports what Mouser
lists for each MPN beside the stock number recorded in
`reference/offers/mouser.yaml`; it never edits the dataset.

    MOUSER_API_KEY=... python -m tools.mouser --out mouser.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from tools.loader import load_dataset

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
    parser.add_argument("--out", type=Path, default=Path("mouser.json"))
    args = parser.parse_args(argv)

    key = os.environ.get("MOUSER_API_KEY")
    if not key:
        print("MOUSER_API_KEY is not set", file=sys.stderr)
        return 2

    dataset, _ = load_dataset(args.root)
    recorded = dataset.offers.get("mouser", {})
    parts = sorted(dataset.parts.values(), key=lambda part: part.mpn)

    report: list[dict] = []
    for start in range(0, len(parts), BATCH):
        batch = parts[start : start + BATCH]
        response = search([part.mpn for part in batch], key)
        if response.get("Errors"):
            print(json.dumps(response["Errors"]), file=sys.stderr)
            return 1
        report.extend(
            summarise(part.mpn, recorded.get(part.id), response) for part in batch
        )

    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    table = markdown(report)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("## Mouser lookup\n\n" + table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
