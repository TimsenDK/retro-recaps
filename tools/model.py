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
    designators_unknown: bool = False
    original_voltage_v: float | None = None
    original_voltage_unknown: bool = False
    max_height_mm: float | None = None
    max_diameter_mm: float | None = None
    max_lead_spacing_mm: float | None = None
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
            designators_unknown=bool(document.get("designators_unknown", False)),
            original_voltage_v=document.get("original_voltage_v"),
            original_voltage_unknown=bool(
                document.get("original_voltage_unknown", False)
            ),
            max_height_mm=document.get("max_height_mm"),
            max_diameter_mm=document.get("max_diameter_mm"),
            max_lead_spacing_mm=document.get("max_lead_spacing_mm"),
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
    mains: bool | None = None
    x2_filter: str | None = None
    battery: bool | None = None
    external: bool = False
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
            mains=document.get("mains"),
            x2_filter=document.get("x2_filter"),
            battery=document.get("battery"),
            external=bool(document.get("external", False)),
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

    @property
    def carries_mains(self) -> bool:
        """Whether this PCB must warn about mains voltage.

        An explicit declaration always wins. Board kind is only a fallback,
        and a poor one: the 1541 longboard mainboard carries the machine's
        linear supply, while the 1541-II analog board is low-voltage motor
        control. Falling back on ``psu`` alone keeps an undeclared supply
        warning rather than falling silent.
        """
        if self.mains is not None:
            return self.mains
        return self.board == "psu"


@dataclass(frozen=True)
class LayoutFeature:
    """One thing drawn on a board map, placed in normalised coordinates."""

    kind: str
    x: float
    y: float
    designator: str | None = None
    label: str | None = None
    approximate: bool = False


@dataclass(frozen=True)
class Layout:
    """Where the parts of one board sit, as read off a source.

    Separate from the board it describes: the geometry has its own source,
    its own accuracy and its own way of being wrong.
    """

    id: str
    board: str
    precision: str
    verification: str
    orientation: str
    width: float
    height: float
    features: tuple[LayoutFeature, ...]
    sources: tuple[Source, ...] = ()
    notes: tuple[str, ...] = ()
    path: Path | None = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, document: dict, path: Path | None = None) -> Layout:
        outline = document["outline"]
        return cls(
            id=document["id"],
            board=document["board"],
            precision=document["precision"],
            verification=document["verification"],
            orientation=document["orientation"],
            width=float(outline["width"]),
            height=float(outline["height"]),
            features=tuple(
                LayoutFeature(
                    kind=feature["kind"],
                    x=float(feature["x"]),
                    y=float(feature["y"]),
                    designator=feature.get("designator"),
                    label=feature.get("label"),
                    approximate=bool(feature.get("approximate", False)),
                )
                for feature in document.get("features", ())
            ),
            sources=tuple(
                Source.from_dict(item) for item in document.get("sources", ())
            ),
            notes=tuple(document.get("notes", ())),
            path=path,
        )

    @property
    def designators(self) -> frozenset[str]:
        """Every capacitor designator this map places."""
        return frozenset(
            feature.designator
            for feature in self.features
            if feature.kind == "capacitor" and feature.designator
        )


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
    voltage_min_v: float | None = None
    voltage_max_v: float | None = None
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
            voltage_min_v=document.get("voltage_min_v"),
            voltage_max_v=document.get("voltage_max_v"),
            low_esr=document.get("low_esr"),
            note=document.get("note"),
        )

    def covers(self, voltage_v: float) -> bool:
        """Whether the series is made in a part of this working voltage.

        A series with no range recorded covers everything, because silence
        here means nobody has read the datasheet — not that the range is
        unbounded.
        """
        if self.voltage_min_v is not None and voltage_v < self.voltage_min_v:
            return False
        if self.voltage_max_v is not None and voltage_v > self.voltage_max_v:
            return False
        return True

    @property
    def voltage_range(self) -> str | None:
        """'6.3-100 V', or None where no range is recorded.

        A plain hyphen, not an en dash: this string goes into validator
        messages, which land in terminals that are not all UTF-8.
        """
        if self.voltage_min_v is None and self.voltage_max_v is None:
            return None
        low = "?" if self.voltage_min_v is None else f"{self.voltage_min_v:g}"
        high = "?" if self.voltage_max_v is None else f"{self.voltage_max_v:g}"
        return f"{low}-{high} V"


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
    layouts: dict[str, Layout] = field(default_factory=dict)

    def boards_for(self, machine_id: str) -> list[Board]:
        """Boards of one machine, in the order they should be recapped."""
        machine = self.machines[machine_id]
        order = {kind: index for index, kind in enumerate(machine.board_order)}
        boards = [b for b in self.boards.values() if b.machine == machine_id]
        return sorted(boards, key=lambda b: (order.get(b.board, len(order)), b.id))
