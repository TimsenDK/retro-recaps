"""Turning a board position into purchasable parts and links.

Nothing here touches the network. A supplier that has never been curated
still produces a usable search link from the manufacturer part number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from urllib.parse import quote

from tools.model import Capacitor, Dataset, Part

CAPACITANCE_TOLERANCE = 1e-2

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


def candidate_parts(capacitor: Capacitor, dataset: Dataset) -> list[Part]:
    """Parts that will do for this position, best first."""
    if capacitor.part is not None:
        part = dataset.parts.get(capacitor.part)
        return [part] if part is not None else []

    fitting = [part for part in dataset.parts.values() if matches(part, capacitor)]
    return sorted(
        fitting,
        key=lambda part: (
            0 if capacitor.series and part.series == capacitor.series else 1,
            part.voltage_v,
            part.id,
        ),
    )


def supplier_links(part: Part, dataset: Dataset) -> list[SupplierLink]:
    """One link per supplier: the product page if known, a search if not."""
    links: list[SupplierLink] = []
    for supplier in dataset.suppliers.values():
        sku = dataset.offers.get(supplier.id, {}).get(part.id)
        if sku and supplier.product_url:
            url = supplier.product_url.replace("{sku}", quote(sku, safe=""))
            links.append(SupplierLink(supplier.id, url, PRODUCT))
        else:
            url = supplier.search_url.replace("{mpn}", quote(part.mpn, safe=""))
            links.append(SupplierLink(supplier.id, url, SEARCH))
    return links
