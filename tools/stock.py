"""What Mouser had in stock when the site was built.

The stock file is written by :mod:`tools.mouser` just before a build and read
here. It is never part of the dataset: stock changes daily, and a number
committed to the repository would be wrong by the time anyone read it. A
missing or unreadable file is not an error — selection then treats every
part's stock as unknown, which is what a Mouser outage honestly means.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

END_OF_LIFE_WORDS = ("obsolete", "end of life", "eol")
"""Lifecycle statuses that mean a part cannot be bought new.

Matched case-insensitively as substrings, because Mouser's wording varies
("Obsolete", "End of Life", "EOL") and anything else — "New Product",
"Not Recommended for New Designs", no status at all — can still be ordered.
"""


@dataclass(frozen=True)
class StockEntry:
    mouser_part_number: str
    in_stock: int
    lifecycle: str | None = None
    url: str | None = None

    @property
    def end_of_life(self) -> bool:
        return is_end_of_life(self.lifecycle)


@dataclass(frozen=True)
class Stock:
    fetched_at: str | None
    parts: dict[str, StockEntry]

    def get(self, part_id: str) -> StockEntry | None:
        return self.parts.get(part_id)


def is_end_of_life(lifecycle: str | None) -> bool:
    if not lifecycle:
        return False
    lowered = lifecycle.lower()
    return any(word in lowered for word in END_OF_LIFE_WORDS)


def parse_in_stock(value: object) -> int:
    """Mouser sends AvailabilityInStock as a string such as "8387", or nothing.

    Anything that is not a whole number counts as none in stock: a part whose
    availability cannot be read should not outrank one Mouser says it holds.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, str):
        digits = value.strip().replace(",", "")
        if digits.isdigit():
            return int(digits)
    return 0


def stock_from_dict(document: dict) -> Stock:
    parts: dict[str, StockEntry] = {}
    for part_id, entry in (document.get("parts") or {}).items():
        if not isinstance(entry, dict) or not entry.get("mouser_part_number"):
            continue
        parts[part_id] = StockEntry(
            mouser_part_number=entry["mouser_part_number"],
            in_stock=parse_in_stock(entry.get("in_stock")),
            lifecycle=entry.get("lifecycle"),
            url=entry.get("url"),
        )
    return Stock(fetched_at=document.get("fetched_at"), parts=parts)


def load_stock(path: Path | None) -> Stock | None:
    """The stock file at `path`, or None if there is no usable one."""
    if path is None or not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    return stock_from_dict(document)
