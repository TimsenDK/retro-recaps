"""The in-memory shape of the dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Source:
    url: str
    note: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Source:
        return cls(url=document["url"], note=document.get("note"))


@dataclass(frozen=True)
class Battery:
    kind: str
    action: str
    note: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Battery:
        return cls(
            kind=document["kind"],
            action=document["action"],
            note=document.get("note"),
        )


@dataclass(frozen=True)
class Capacitor:
    type: str
    capacitance_uf: float
    voltage_v: float
    quantity: int
    designators: tuple[str, ...] = ()
    original_voltage_v: float | None = None
    series: str | None = None
    part: str | None = None
    verification: str | None = None
    note: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Capacitor:
        return cls(
            type=document["type"],
            capacitance_uf=document["capacitance_uf"],
            voltage_v=document["voltage_v"],
            quantity=document["quantity"],
            designators=tuple(document.get("designators", ())),
            original_voltage_v=document.get("original_voltage_v"),
            series=document.get("series"),
            part=document.get("part"),
            verification=document.get("verification"),
            note=document.get("note"),
        )

    def effective_verification(self, board_verification: str) -> str:
        """A position's own status wins; otherwise it inherits the board's."""
        return self.verification or board_verification

    @property
    def label(self) -> str:
        if self.designators:
            return ", ".join(self.designators)
        return f"{self.quantity} position" + ("s" if self.quantity != 1 else "")


@dataclass(frozen=True)
class Board:
    id: str
    machine: str
    board: str
    revisions: tuple[str, ...]
    verification: str
    capacitors: tuple[Capacitor, ...]
    sources: tuple[Source, ...] = ()
    notes: tuple[str, ...] = ()
    path: Path | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, document: dict, path: Path | None = None) -> Board:
        return cls(
            id=document["id"],
            machine=document["machine"],
            board=document["board"],
            revisions=tuple(document["revisions"]),
            verification=document["verification"],
            capacitors=tuple(
                Capacitor.from_dict(item) for item in document["capacitors"]
            ),
            sources=tuple(
                Source.from_dict(item) for item in document.get("sources", ())
            ),
            notes=tuple(document.get("notes", ())),
            path=path,
        )

    @property
    def total_capacitors(self) -> int:
        return sum(capacitor.quantity for capacitor in self.capacitors)


@dataclass(frozen=True)
class Machine:
    id: str
    name: str
    family: str
    board_order: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    batteries: tuple[Battery, ...] = ()
    path: Path | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, document: dict, path: Path | None = None) -> Machine:
        return cls(
            id=document["id"],
            name=document["name"],
            family=document["family"],
            board_order=tuple(document["board_order"]),
            aliases=tuple(document.get("aliases", ())),
            notes=tuple(document.get("notes", ())),
            batteries=tuple(
                Battery.from_dict(item) for item in document.get("batteries", ())
            ),
            path=path,
        )


@dataclass(frozen=True)
class Series:
    id: str
    manufacturer: str
    name: str
    type: str
    temperature_c: int | None = None
    low_esr: bool | None = None
    note: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Series:
        return cls(
            id=document["id"],
            manufacturer=document["manufacturer"],
            name=document["name"],
            type=document["type"],
            temperature_c=document.get("temperature_c"),
            low_esr=document.get("low_esr"),
            note=document.get("note"),
        )


@dataclass(frozen=True)
class Part:
    id: str
    manufacturer: str
    mpn: str
    series: str
    type: str
    capacitance_uf: float
    voltage_v: float
    diameter_mm: float | None = None
    height_mm: float | None = None
    lead_spacing_mm: float | None = None
    note: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Part:
        return cls(
            id=document["id"],
            manufacturer=document["manufacturer"],
            mpn=document["mpn"],
            series=document["series"],
            type=document["type"],
            capacitance_uf=document["capacitance_uf"],
            voltage_v=document["voltage_v"],
            diameter_mm=document.get("diameter_mm"),
            height_mm=document.get("height_mm"),
            lead_spacing_mm=document.get("lead_spacing_mm"),
            note=document.get("note"),
        )


@dataclass(frozen=True)
class Supplier:
    id: str
    name: str
    search_url: str
    region: str | None = None
    product_url: str | None = None

    @classmethod
    def from_dict(cls, document: dict) -> Supplier:
        return cls(
            id=document["id"],
            name=document["name"],
            search_url=document["search_url"],
            region=document.get("region"),
            product_url=document.get("product_url"),
        )


@dataclass(frozen=True)
class Dataset:
    machines: dict[str, Machine]
    boards: dict[str, Board]
    parts: dict[str, Part]
    series: dict[str, Series]
    suppliers: dict[str, Supplier]
    offers: dict[str, dict[str, str]]

    def boards_for(self, machine_id: str) -> list[Board]:
        """Boards of one machine, in the order they should be recapped."""
        machine = self.machines[machine_id]
        order = {kind: index for index, kind in enumerate(machine.board_order)}
        boards = [b for b in self.boards.values() if b.machine == machine_id]
        return sorted(boards, key=lambda b: (order.get(b.board, len(order)), b.id))
