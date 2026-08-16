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


def _matches(part: Part, capacitor: Capacitor) -> bool:
    if part.type != capacitor.type:
        return False
    if not math.isclose(
        part.capacitance_uf,
        capacitor.capacitance_uf,
        rel_tol=CAPACITANCE_TOLERANCE,
    ):
        return False
    return part.voltage_v >= capacitor.voltage_v


def candidate_parts(capacitor: Capacitor, dataset: Dataset) -> list[Part]:
    """Parts that will do for this position, best first."""
    if capacitor.part is not None:
        part = dataset.parts.get(capacitor.part)
        return [part] if part is not None else []

    matches = [part for part in dataset.parts.values() if _matches(part, capacitor)]
    return sorted(
        matches,
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
