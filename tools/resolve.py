"""Turning a board position into purchasable parts and links.

Nothing here touches the network. A supplier that has never been curated
still produces a usable search link from the manufacturer part number, and
stock, where it is known at all, arrives as a :class:`tools.stock.Stock`
read from a file written before the build.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import quote

from tools.model import Capacitor, Dataset, Part
from tools.stock import Stock

CAPACITANCE_TOLERANCE = 1e-2

PREFERRED_MANUFACTURERS = ("Nichicon", "Panasonic", "Würth Elektronik", "Kemet")
"""The owner's preferred brands, one tier: none of the four outranks another.

Any other quality brand is still offered, but only after these where stock and
hybrid construction are equal. The names must match `manufacturer` exactly.
"""

IN_STOCK = 0
STOCK_UNKNOWN = 1
OUT_OF_STOCK = 2

PRODUCT = "product"
SEARCH = "search"


@dataclass(frozen=True)
class SupplierLink:
    supplier_id: str
    url: str
    kind: str


def same_capacitance(left: float, right: float) -> bool:
    """Capacitance is written as a float in YAML, so compare with tolerance."""
    return math.isclose(left, right, rel_tol=CAPACITANCE_TOLERANCE)


FIT_DIMENSIONS = (
    ("height", "height_mm", "max_height_mm"),
    ("diameter", "diameter_mm", "max_diameter_mm"),
    ("lead spacing", "lead_spacing_mm", "max_lead_spacing_mm"),
)
"""(label, the part's field, the position's limit) for each physical dimension."""


def fit_violations(
    part: Part, capacitor: Capacitor
) -> list[tuple[str, float, float]]:
    """Every stated dimension limit this part exceeds, as (label, value, limit).

    A dimension the part does not declare never counts as a violation. The
    catalogue is allowed to be incomplete, and dropping every candidate whose
    height nobody has recorded would be worse than offering it.
    """
    violations: list[tuple[str, float, float]] = []
    for label, part_field, limit_field in FIT_DIMENSIONS:
        limit = getattr(capacitor, limit_field)
        value = getattr(part, part_field)
        if limit is None or value is None:
            continue
        if value > limit:
            violations.append((label, value, limit))
    return violations


def matches_electrically(part: Part, capacitor: Capacitor) -> bool:
    """Type, capacitance and voltage — everything but physical fit."""
    if part.type != capacitor.type:
        return False
    if not same_capacitance(part.capacitance_uf, capacitor.capacitance_uf):
        return False
    return part.voltage_v >= capacitor.voltage_v


def matches(part: Part, capacitor: Capacitor) -> bool:
    """Whether this part will do for this position.

    The single definition of fit. ``rules`` uses it too, so a pinned part can
    never pass validation and then be rejected by :func:`candidate_parts`.
    """
    if not matches_electrically(part, capacitor):
        return False
    return not fit_violations(part, capacitor)


def stock_state(part: Part, stock: Stock | None) -> int:
    """In stock, unknown or out of stock, in the order selection prefers them.

    Unknown sits between the two: no stock file, or Mouser not listing the
    MPN, says nothing about whether the part can be bought elsewhere, so it
    must not sink below a part Mouser has confirmed it cannot supply.
    """
    entry = stock.get(part.id) if stock is not None else None
    if entry is None:
        return STOCK_UNKNOWN
    return IN_STOCK if entry.in_stock > 0 else OUT_OF_STOCK


def is_hybrid(part: Part, dataset: Dataset) -> bool:
    series = dataset.series.get(part.series)
    return series is not None and series.hybrid


def candidate_parts(
    capacitor: Capacitor, dataset: Dataset, stock: Stock | None = None
) -> list[Part]:
    """Parts that will do for this position, best first.

    A pinned part is an override and is returned alone, whatever its stock.
    Otherwise fit decides what is offered and the sort decides what is shown
    first: something buyable today, then a hybrid where the position allows
    one, then a preferred brand, then the series the position names, then the
    lowest sufficient voltage and the shortest body.
    """
    if capacitor.part is not None:
        part = dataset.parts.get(capacitor.part)
        return [part] if part is not None else []

    fitting = []
    for part in dataset.parts.values():
        if not matches(part, capacitor):
            continue
        if not capacitor.allow_hybrid and is_hybrid(part, dataset):
            continue
        entry = stock.get(part.id) if stock is not None else None
        if entry is not None and entry.end_of_life:
            continue
        fitting.append(part)

    return sorted(
        fitting,
        key=lambda part: (
            stock_state(part, stock),
            0 if is_hybrid(part, dataset) else 1,
            0 if part.manufacturer in PREFERRED_MANUFACTURERS else 1,
            0 if capacitor.series and part.series == capacitor.series else 1,
            part.voltage_v,
            (0, part.height_mm) if part.height_mm is not None else (1, 0.0),
            part.id,
        ),
    )


def supplier_links(
    part: Part, dataset: Dataset, stock: Stock | None = None
) -> list[SupplierLink]:
    """One link per supplier: the product page if known, a search if not.

    The offers file is curated and wins. Mouser's own number from the stock
    file fills in where nobody has recorded one, so a part found by the
    lookup still links straight to its product page.
    """
    links: list[SupplierLink] = []
    for supplier in dataset.suppliers.values():
        sku = dataset.offers.get(supplier.id, {}).get(part.id)
        if not sku and supplier.id == "mouser" and stock is not None:
            entry = stock.get(part.id)
            sku = entry.mouser_part_number if entry is not None else None
        if sku and supplier.product_url:
            url = supplier.product_url.replace("{sku}", quote(sku, safe=""))
            links.append(SupplierLink(supplier.id, url, PRODUCT))
        else:
            url = supplier.search_url.replace("{mpn}", quote(part.mpn, safe=""))
            links.append(SupplierLink(supplier.id, url, SEARCH))
    return links
