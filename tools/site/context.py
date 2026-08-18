"""View models for the site.

Everything the site knows how to work out — grouping, ordering, counting, the
verification roll-up, which page carries which warning — is decided here, in
plain dataclasses. No Jinja, no HTML, no filesystem. The templates present
what this module hands them and compute nothing of their own, which is what
makes the site's behaviour testable without rendering a page.

The dataset is the truth. Nothing in this module infers a value the data does
not state. Where it names something the data only identifies by id — a family,
a board kind, a capacitor type — that is a label for a known id, and an
unknown id falls back to the id itself rather than to a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from tools.model import Board, Capacitor, Dataset, Layout, Machine, Part, Series, Source
from tools.site.layout import LayoutView, layout_view

VERIFICATION_ORDER = ("verified", "derived", "unverified")
"""Best to worst. Anything unrecognised sorts after all of these."""

FAMILY_ORDER = (
    "amiga",
    "commodore-8bit",
    "commodore-drive",
    "macintosh",
)

FAMILY_NAMES = {
    "amiga": "Amiga",
    "commodore-8bit": "Commodore 8-bit",
    "commodore-drive": "Commodore drives",
    "macintosh": "Macintosh",
}

BOARD_KIND_NAMES = {
    "mainboard": "Mainboard",
    "logic": "Logic board",
    "daughterboard": "Daughterboard",
    # A paddle is not a daughterboard: it does not sit on another board at
    # all. It is the PCB on the end of a drive cable that plugs into the
    # computer, and calling it what its own machine's documentation calls it
    # is how a reader finds it in their hand.
    "paddle": "Paddle",
    "analog": "Analog board",
    "psu": "Power supply",
}

CAPACITOR_TYPE_NAMES = {
    "electrolytic-radial": "Electrolytic, radial",
    "electrolytic-axial": "Electrolytic, axial",
    "electrolytic-snap-in": "Electrolytic, snap-in",
    "electrolytic-smd": "Electrolytic, surface mount",
    "bipolar": "Bipolar electrolytic",
    "tantalum": "Tantalum",
    "film": "Film",
    "film-x2": "Film, X2 (mains rated, across the line)",
    "film-y2": "Film, Y2 (mains rated, across the isolation barrier)",
    "ceramic": "Ceramic",
}

POLARISED_TYPES = frozenset(
    {
        "electrolytic-radial",
        "electrolytic-axial",
        "electrolytic-snap-in",
        "electrolytic-smd",
        "tantalum",
    }
)
"""Capacitor types that go in one way round and are destroyed the other.

Read off the type enum rather than off a field, because the dataset does not
record polarity per position — the type already decides it. `bipolar` is an
electrolytic with no polarity, and film, ceramic and the mains classes have
none either, so a board holding only those needs no polarity diagram.

Tantalums are in the list and are the reason the diagram cannot stand alone:
they mark the plus lead where an aluminium electrolytic marks the minus.
"""

CRT_FAMILIES = frozenset({"macintosh"})
"""Families whose machines are all-in-ones with a CRT in the case.

This is a safety judgement made by the site, not a field in the dataset: the
machine files do not record whether a machine has a tube. It is kept here, as
a named constant, so it is visible and can be corrected — rather than being
buried in a template as an `if family == ...`.
"""

BATTERY_BOARD_KINDS = frozenset({"mainboard", "logic"})
"""Board kinds that may carry a machine's battery, for validation only.

Which board a cell is actually soldered to is recorded per board, in
``battery``. Board kind was tried as a proxy and was wrong in exactly the way
board kind is always wrong here: it put a battery warning on the A500 rev 3,
rev 5 and rev 6A pages, none of which have a cell, hedged with a note telling
the reader to go and check. A warning that cannot say whether it applies
teaches the reader to skip warnings.
"""


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def format_number(value: float) -> str:
    """A capacitance or voltage as it is written on a board, not as a float."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def format_capacitance(value: float) -> str:
    return f"{format_number(value)} µF"


def format_voltage(value: float) -> str:
    return f"{format_number(value)} V"


def label_for(mapping: dict[str, str], key: str) -> str:
    return mapping.get(key, key)


def family_mark(family_id: str) -> str | None:
    """The silhouette drawn for a family, relative to the site root.

    Decorative: the family name is in the markup beside it in every case, so
    a family with no drawing loses nothing. One exists per id in
    ``FAMILY_NAMES`` and a new family gets none until someone draws it.
    """
    if family_id not in FAMILY_NAMES:
        return None
    return f"assets/img/family-{family_id}.svg"


def natural_key(text: str) -> tuple:
    """Sort 'Amiga 500' before 'Amiga 1000', which a plain sort does not."""
    parts: list[object] = []
    for chunk in re.split(r"(\d+)", text.lower()):
        if not chunk:
            continue
        parts.append((0, int(chunk), "") if chunk.isdigit() else (1, 0, chunk))
    return tuple(parts)


# --------------------------------------------------------------------------
# Cross-file references in notes
# --------------------------------------------------------------------------

DATA_REFERENCE_RE = re.compile(
    r"(?<![\w/.-])"
    r"(?P<machine>[a-z0-9]+(?:-[a-z0-9]+)*)"
    r"/"
    r"(?P<file>[a-z0-9]+(?:[-.][a-z0-9]+)*)"
    r"\.yaml"
    r"(?![\w/-])"
)
"""The one shape a note may use to name another file: ``<machine>/<file>.yaml``,
the path relative to ``data/``.

A bare ``psu.yaml`` cannot be resolved without knowing which machine the reader
is on, and ``../commodore-128/mainboard-rev6.yaml`` encodes the writer's
position in the tree rather than the thing referred to. One form that is
absolute within ``data/`` is resolvable from anywhere, which is what lets the
generator turn it into a link. See CONTRIBUTING.md.
"""


@dataclass(frozen=True)
class NoteSegment:
    """A run of note text, optionally standing for another page.

    The context does not build HTML; it says which runs are links and what
    they point at, and the template makes the anchor.
    """

    text: str
    url: str | None = None
    """Relative to the site root, like every other url in this module. The
    template prepends the page's own ``base``."""

    @property
    def is_link(self) -> bool:
        return self.url is not None


@dataclass(frozen=True)
class NoteView:
    text: str
    segments: tuple[NoteSegment, ...]

    @property
    def has_links(self) -> bool:
        return any(segment.is_link for segment in self.segments)


def reference_targets(dataset: Dataset) -> dict[str, tuple[str, str]]:
    """Map every ``<machine>/<file>.yaml`` a note may name to (url, label)."""
    targets: dict[str, tuple[str, str]] = {}
    for machine in dataset.machines.values():
        targets[f"{machine.id}/machine.yaml"] = (
            f"{machine.id}/index.html",
            machine.name,
        )
    kind_counts: dict[tuple[str, str], int] = {}
    for board in dataset.boards.values():
        key = (board.machine, board.board)
        kind_counts[key] = kind_counts.get(key, 0) + 1
    for board in dataset.boards.values():
        slug = _board_slug(board)
        machine = dataset.machines.get(board.machine)
        machine_name = machine.name if machine is not None else board.machine
        label = f"{machine_name} — {label_for(BOARD_KIND_NAMES, board.board)}"
        if kind_counts[(board.machine, board.board)] > 1 and board.revisions:
            label = f"{label} {', '.join(board.revisions)}"
        targets[f"{board.machine}/{slug}.yaml"] = (
            f"{board.machine}/{slug}.html",
            label,
        )
    return targets


def note_view(note: str, targets: dict[str, tuple[str, str]]) -> NoteView:
    """Split a note into plain runs and links to the files it names.

    A reference that names no file in the dataset is left exactly as written:
    a broken link on a printed sheet is worse than a filename the reader can
    still search for.
    """
    segments: list[NoteSegment] = []
    cursor = 0
    for match in DATA_REFERENCE_RE.finditer(note):
        target = targets.get(match.group(0))
        if target is None:
            continue
        url, label = target
        if match.start() > cursor:
            segments.append(NoteSegment(note[cursor : match.start()]))
        segments.append(NoteSegment(label, url))
        cursor = match.end()
    if cursor < len(note):
        segments.append(NoteSegment(note[cursor:]))
    return NoteView(text=note, segments=tuple(segments))


def note_views(
    notes: tuple[str, ...], targets: dict[str, tuple[str, str]]
) -> tuple[NoteView, ...]:
    return tuple(note_view(note, targets) for note in notes)


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

Tone = Literal["verified", "caution", "warning", "unknown"]


@dataclass(frozen=True)
class VerificationView:
    """A verification status, and what a reader should do about it.

    The tone is deliberately not a shade of the same colour for every status.
    `derived` means nobody has confirmed the list against a source for this
    exact board revision; a reader who reads that as a slightly duller tick
    can fit the wrong part.
    """

    status: str
    label: str
    tone: Tone
    headline: str
    guidance: str


_VERIFICATION_VIEWS = {
    "verified": VerificationView(
        status="verified",
        label="Verified",
        tone="verified",
        headline="Checked against a cited source for this board revision.",
        guidance=(
            "Every position below comes from a source listed at the foot of "
            "this page. Still confirm polarity and physical fit against the "
            "board in front of you before you order."
        ),
    ),
    "derived": VerificationView(
        status="derived",
        label="Derived — not confirmed",
        tone="caution",
        headline="Nobody has confirmed this list against this board revision.",
        guidance=(
            "The values here were worked out from related boards, partial "
            "sources or general practice. Count the positions on your own "
            "board and read the values off the capacitors before ordering. "
            "Treat this page as a starting point, not as an answer."
        ),
    ),
    "unverified": VerificationView(
        status="unverified",
        label="Unverified — do not order from this",
        tone="warning",
        headline="No source establishes this list.",
        guidance=(
            "Nothing here has been checked. Count and measure the board "
            "yourself before you buy anything, and please contribute what you "
            "find so the next person does not have to."
        ),
    ),
}


def verification_view(status: str) -> VerificationView:
    known = _VERIFICATION_VIEWS.get(status)
    if known is not None:
        return known
    return VerificationView(
        status=status,
        label=status,
        tone="unknown",
        headline="This status is not one the site knows how to explain.",
        guidance=(
            "Check the board's own file for what this status means before "
            "relying on the list."
        ),
    )


@dataclass(frozen=True)
class Coverage:
    """How much of a machine, family or the site is actually established."""

    verified: int = 0
    derived: int = 0
    unverified: int = 0
    other: int = 0
    empty: int = 0

    @property
    def total(self) -> int:
        return self.verified + self.derived + self.unverified + self.other

    @property
    def worst(self) -> str:
        """The status a reader should assume for the group as a whole.

        One unverified board in a machine means the machine is not settled,
        however many verified boards sit beside it.
        """
        if self.unverified or self.other:
            return "unverified" if self.unverified else "unknown"
        if self.derived:
            return "derived"
        if self.verified:
            return "verified"
        return "unknown"

    @property
    def view(self) -> VerificationView:
        return verification_view(self.worst)

    @property
    def tone(self) -> Tone:
        if self.empty:
            return "warning"
        return self.view.tone

    @property
    def group_label(self) -> str:
        """A badge for a machine or family, not for a single board.

        A machine with three verified boards and one unverified one is not
        'unverified' — but it is not settled either, and the badge has to say
        so without claiming the verified boards are in doubt.
        """
        if not self.total:
            return "No boards yet"
        if self.unverified or self.other:
            return "Not established throughout"
        if self.derived:
            if self.derived == self.total:
                return "All derived — none confirmed"
            return "Partly derived"
        return "All verified"

    @property
    def group_headline(self) -> str:
        if not self.total:
            return "No board files exist here yet."
        if self.empty:
            boards = "board" if self.empty == 1 else "boards"
            return (
                f"{self.empty} {boards} here have no capacitor list at all, "
                f"and others may still be unconfirmed. Read each board's own "
                f"badge before you order."
            )
        if self.unverified or self.other:
            return (
                "At least one board here has nothing established behind it. "
                "Read each board's own badge before you order."
            )
        if self.derived:
            if self.derived == self.total:
                return (
                    "Nothing here has been confirmed against the board "
                    "revisions it describes. Count before you order."
                )
            return (
                "Some boards here are confirmed and some are not. Read each "
                "board's own badge before you order."
            )
        return (
            "Every board here was read off a source cited on its own page. "
            "Still check polarity and fit against your board."
        )

    @property
    def summary(self) -> str:
        """A plain count, e.g. '3 boards — 1 verified, 2 derived'."""
        if not self.total:
            return "No boards"
        parts = []
        for name, count in (
            ("verified", self.verified),
            ("derived", self.derived),
            ("unverified", self.unverified),
        ):
            if count:
                parts.append(f"{count} {name}")
        if self.other:
            parts.append(f"{self.other} other")
        board_word = "board" if self.total == 1 else "boards"
        return f"{self.total} {board_word} — " + ", ".join(parts)


def coverage_for(boards: list[Board]) -> Coverage:
    counts = {"verified": 0, "derived": 0, "unverified": 0}
    other = 0
    empty = 0
    for board in boards:
        if board.verification in counts:
            counts[board.verification] += 1
        else:
            other += 1
        if not board.capacitors:
            empty += 1
    return Coverage(other=other, empty=empty, **counts)


# --------------------------------------------------------------------------
# Hazards
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Hazard:
    id: str
    title: str
    body: str


MAINS_HAZARD = Hazard(
    id="mains",
    title="Mains voltage",
    body=(
        "This board carries mains voltage when the machine is plugged in, "
        "and its filter capacitors hold a dangerous charge after it is "
        "switched off and unplugged. Unplug at the wall, discharge "
        "deliberately through a resistor, and measure before you touch "
        "anything."
    ),
)

CRT_ANALOG_HAZARD = Hazard(
    id="crt-analog",
    title="Mains and CRT voltage",
    body=(
        "This analog board drives a CRT and carries mains-derived voltages. "
        "The tube's anode holds a very high voltage long after the machine is "
        "unplugged, and the tube can implode if broken. Discharge the CRT "
        "properly before working on this board, or have someone experienced "
        "do it."
    ),
)

ANALOG_HAZARD = Hazard(
    id="analog",
    title="Check what this board carries",
    body=(
        "Analog boards differ from machine to machine, and this one is not "
        "documented as low voltage anywhere in the dataset. Unplug the "
        "machine and measure before you assume any part of it is safe to "
        "touch."
    ),
)

MACHINE_MAINS_HAZARD_ID = "machine-mains"
"""The machine-page counterpart of ``MAINS_HAZARD``.

The board-page panel opens "This board carries mains voltage", which has no
referent on a machine page — that page names no board. Worse, a machine can
hold a mains board a reader never touches: the 1541-II's supply is a sealed,
resin-potted external brick, replaced as a unit. So the machine panel says
*which* boards carry mains and sends the reader to those pages, rather than
asserting anything about the machine as a whole.
"""


def machine_mains_hazard(boards: list[Board]) -> Hazard:
    """The mains panel for a machine page, naming the boards it applies to."""
    names: list[str] = []
    for board in boards:
        if not board.carries_mains or board.external:
            continue
        name = label_for(BOARD_KIND_NAMES, board.board).lower()
        if name not in names:
            names.append(name)
    if len(names) > 1:
        which = ", ".join(names[:-1]) + f" and {names[-1]}"
        subject = f"Some of this machine's boards carry mains voltage: the {which}."
        where = "on those boards"
        follow = "Read those board pages before you open the case"
    elif names:
        subject = f"This machine's {names[0]} carries mains voltage."
        where = "on it"
        follow = f"Read the {names[0]} page before you open the case"
    else:
        subject = "One of this machine's boards carries mains voltage."
        where = "on it"
        follow = "Read each board page before you open the case"
    return Hazard(
        id=MACHINE_MAINS_HAZARD_ID,
        title="Mains voltage inside this machine",
        body=(
            f"{subject} The filter capacitors {where} hold a dangerous charge "
            f"after the machine is switched off and unplugged. "
            f"{follow}, and treat anything you have not identified as live."
        ),
    )


CRT_MACHINE_HAZARD = Hazard(
    id="crt",
    title="This machine has a CRT",
    body=(
        "Even with this board out of the case, the tube holds a very high "
        "voltage on its anode long after the machine is unplugged, and can "
        "implode if broken. Discharge the CRT properly before reaching past "
        "it."
    ),
)


def hazards_for(board: Board, machine: Machine | None) -> tuple[Hazard, ...]:
    """Every warning a board page must carry, strongest first.

    Driven by the board's own ``mains`` declaration rather than by its kind.
    A CRT analog board gets both warnings, not one instead of the other: on
    an all-in-one Mac the analog board *is* the supply, so discharging the
    tube and then grabbing the board still leaves a charged bulk capacitor
    between the reader and the bench.
    """
    family = machine.family if machine is not None else ""
    is_crt = family in CRT_FAMILIES
    hazards: list[Hazard] = []

    if board.board == "analog" and is_crt:
        hazards.append(CRT_ANALOG_HAZARD)
        if board.carries_mains:
            hazards.append(MAINS_HAZARD)
        return tuple(hazards)

    if board.carries_mains:
        hazards.append(MAINS_HAZARD)
    elif board.board == "analog" and board.mains is None:
        hazards.append(ANALOG_HAZARD)

    if is_crt:
        hazards.append(CRT_MACHINE_HAZARD)
    return tuple(hazards)


def machine_hazards(boards: list[Board], machine: Machine) -> tuple[Hazard, ...]:
    """The warning a machine page carries, given the boards it holds.

    Only mains *inside the case* counts. An A500, a C128 or a 1541-II runs
    from a sealed external brick: the brick's own page warns about it, but
    someone opening the machine is never near mains. Telling them otherwise
    is how a warning stops being read.
    """
    hazards: list[Hazard] = []
    if any(board.carries_mains and not board.external for board in boards):
        hazards.append(machine_mains_hazard(boards))
    if machine.family in CRT_FAMILIES:
        hazards.append(CRT_MACHINE_HAZARD)
    return tuple(hazards)


# --------------------------------------------------------------------------
# Board pages
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SeriesView:
    id: str
    name: str
    manufacturer: str
    type_label: str
    temperature_c: int | None
    voltage_range: str | None
    low_esr: bool | None
    note: str | None

    @property
    def display(self) -> str:
        return f"{self.manufacturer} {self.name}"


def series_view(series: Series) -> SeriesView:
    return SeriesView(
        id=series.id,
        name=series.name,
        manufacturer=series.manufacturer,
        type_label=label_for(CAPACITOR_TYPE_NAMES, series.type),
        temperature_c=series.temperature_c,
        voltage_range=series.voltage_range,
        low_esr=series.low_esr,
        note=series.note,
    )


@dataclass(frozen=True)
class PartView:
    id: str
    manufacturer: str
    mpn: str
    series_display: str
    type_label: str
    capacitance: str
    voltage: str
    dimensions: str | None
    note: str | None


@dataclass(frozen=True)
class CapacitorRow:
    """One line of a board's capacitor table."""

    designators: tuple[str, ...]
    designator_label: str
    has_designators: bool
    quantity: int
    capacitance: str
    voltage: str
    original_voltage_note: str | None
    type_id: str
    type_label: str
    is_polarised: bool
    series: SeriesView | None
    series_label: str
    part: PartView | None
    fit_limits: tuple[str, ...]
    note: str | None
    verification: VerificationView
    differs_from_board: bool

    @property
    def icon_url(self) -> str | None:
        """The type symbol drawn for this type, relative to the site root.

        One drawing exists per value of the type enum, named after it. A type
        the site has no name for has no drawing either, and gets none rather
        than a broken image — the written label carries the meaning in every
        case, and the symbol only ever supplements it.
        """
        if self.type_id not in CAPACITOR_TYPE_NAMES:
            return None
        return f"assets/img/cap-{self.type_id}.svg"


def _fit_limits(capacitor: Capacitor) -> tuple[str, ...]:
    limits = []
    if capacitor.max_height_mm is not None:
        limits.append(f"max height {format_number(capacitor.max_height_mm)} mm")
    if capacitor.max_diameter_mm is not None:
        limits.append(f"max diameter {format_number(capacitor.max_diameter_mm)} mm")
    if capacitor.max_lead_spacing_mm is not None:
        limits.append(
            f"max lead spacing {format_number(capacitor.max_lead_spacing_mm)} mm"
        )
    return tuple(limits)


def _part_view(part: Part, dataset: Dataset) -> PartView:
    series = dataset.series.get(part.series)
    dimensions = None
    if part.diameter_mm is not None and part.height_mm is not None:
        dimensions = (
            f"{format_number(part.diameter_mm)} × "
            f"{format_number(part.height_mm)} mm"
        )
    return PartView(
        id=part.id,
        manufacturer=part.manufacturer,
        mpn=part.mpn,
        series_display=(
            f"{series.manufacturer} {series.name}" if series else part.series
        ),
        type_label=label_for(CAPACITOR_TYPE_NAMES, part.type),
        capacitance=format_capacitance(part.capacitance_uf),
        voltage=format_voltage(part.voltage_v),
        dimensions=dimensions,
        note=part.note,
    )


def capacitor_row(
    capacitor: Capacitor, board: Board, dataset: Dataset
) -> CapacitorRow:
    effective = capacitor.effective_verification(board.verification)
    series = dataset.series.get(capacitor.series) if capacitor.series else None
    part = dataset.parts.get(capacitor.part) if capacitor.part else None
    original = None
    if (
        capacitor.original_voltage_v is not None
        and capacitor.original_voltage_v != capacitor.voltage_v
    ):
        original = f"was {format_voltage(capacitor.original_voltage_v)}"
    return CapacitorRow(
        designators=capacitor.designators,
        designator_label=capacitor.label,
        has_designators=bool(capacitor.designators),
        quantity=capacitor.quantity,
        capacitance=format_capacitance(capacitor.capacitance_uf),
        voltage=format_voltage(capacitor.voltage_v),
        original_voltage_note=original,
        type_id=capacitor.type,
        type_label=label_for(CAPACITOR_TYPE_NAMES, capacitor.type),
        is_polarised=capacitor.type in POLARISED_TYPES,
        series=series_view(series) if series else None,
        series_label=(
            f"{series.manufacturer} {series.name}"
            if series
            else (capacitor.series or "")
        ),
        part=_part_view(part, dataset) if part else None,
        fit_limits=_fit_limits(capacitor),
        note=capacitor.note,
        verification=verification_view(effective),
        differs_from_board=effective != board.verification,
    )


def _designator_sort_key(designators: tuple[str, ...]) -> tuple:
    """Sort C7 before C11, and a row without designators last."""
    if not designators:
        return (1, "", 0, "")
    first = designators[0]
    prefix = "".join(ch for ch in first if not ch.isdigit())
    digits = "".join(ch for ch in first if ch.isdigit())
    return (0, prefix, int(digits) if digits else 0, first)


@dataclass(frozen=True)
class BoardView:
    id: str
    slug: str
    machine_id: str
    machine_name: str
    family: str
    family_name: str
    kind: str
    kind_label: str
    title: str
    revision_label: str
    revisions: tuple[str, ...]
    url: str
    machine_url: str
    yaml_url: str
    json_url: str
    verification: VerificationView
    rows: tuple[CapacitorRow, ...]
    position_count: int
    capacitor_count: int
    is_empty: bool
    open_question: str | None
    hazards: tuple[Hazard, ...]
    sources: tuple[Source, ...]
    notes: tuple[str, ...]
    linked_notes: tuple[NoteView, ...]
    batteries: tuple
    rows_without_designators: int
    mixed_verification: bool
    layout: LayoutView | None = None

    @property
    def has_polarised(self) -> bool:
        """Whether any position on this board can be fitted the wrong way.

        A board of film and ceramic parts gets no polarity diagram: an
        instruction that does not apply is one more thing to read past on a
        page that is trying to be a checklist.
        """
        return any(row.is_polarised for row in self.rows)


EMPTY_LIST_QUESTION = (
    "No capacitor list is established for this board. That is the point of "
    "this page: the positions have not been counted and no source settles "
    "them, so there is nothing here to order from. Read the notes below for "
    "what is known, count the board in front of you, and please contribute "
    "the result."
)


def _board_slug(board: Board) -> str:
    if board.path is not None:
        return board.path.stem
    prefix = f"{board.machine}-"
    if board.id.startswith(prefix):
        return board.id[len(prefix) :]
    return board.id


def board_view(
    board: Board,
    dataset: Dataset,
    *,
    disambiguate: bool,
    targets: dict[str, tuple[str, str]] | None = None,
    layout: Layout | None = None,
) -> BoardView:
    if targets is None:
        targets = reference_targets(dataset)
    machine = dataset.machines.get(board.machine)
    machine_name = machine.name if machine is not None else board.machine
    kind_label = label_for(BOARD_KIND_NAMES, board.board)
    revision_label = ", ".join(board.revisions)
    title = kind_label
    if disambiguate and revision_label:
        title = f"{kind_label} — {revision_label}"
    slug = _board_slug(board)
    rows = tuple(
        sorted(
            (capacitor_row(c, board, dataset) for c in board.capacitors),
            key=lambda row: _designator_sort_key(row.designators),
        )
    )
    return BoardView(
        id=board.id,
        slug=slug,
        machine_id=board.machine,
        machine_name=machine_name,
        family=machine.family if machine is not None else "",
        family_name=(
            label_for(FAMILY_NAMES, machine.family) if machine is not None else ""
        ),
        kind=board.board,
        kind_label=kind_label,
        title=title,
        revision_label=revision_label,
        revisions=board.revisions,
        url=f"{board.machine}/{slug}.html",
        machine_url=f"{board.machine}/index.html",
        yaml_url=f"{board.machine}/{slug}.yaml",
        json_url=f"{board.machine}/{slug}.json",
        verification=verification_view(board.verification),
        rows=rows,
        position_count=len(board.capacitors),
        capacitor_count=board.total_capacitors,
        is_empty=not board.capacitors,
        open_question=EMPTY_LIST_QUESTION if not board.capacitors else None,
        hazards=hazards_for(board, machine),
        sources=board.sources,
        notes=board.notes,
        linked_notes=note_views(board.notes, targets),
        batteries=(
            machine.batteries if machine is not None and board.battery else ()
        ),
        rows_without_designators=sum(1 for row in rows if not row.has_designators),
        mixed_verification=any(row.differs_from_board for row in rows),
        layout=layout_view(layout) if layout is not None else None,
    )


# --------------------------------------------------------------------------
# Machine and family pages
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MachineView:
    id: str
    name: str
    family: str
    family_name: str
    aliases: tuple[str, ...]
    notes: tuple[str, ...]
    linked_notes: tuple[NoteView, ...]
    batteries: tuple
    url: str
    boards: tuple[BoardView, ...]
    coverage: Coverage
    hazards: tuple[Hazard, ...]

    @property
    def capacitor_count(self) -> int:
        return sum(board.capacitor_count for board in self.boards)

    @property
    def family_mark_url(self) -> str | None:
        return family_mark(self.family)


@dataclass(frozen=True)
class FamilyView:
    id: str
    name: str
    machines: tuple[MachineView, ...]

    @property
    def mark_url(self) -> str | None:
        return family_mark(self.id)

    @property
    def coverage(self) -> Coverage:
        return Coverage(
            verified=sum(m.coverage.verified for m in self.machines),
            derived=sum(m.coverage.derived for m in self.machines),
            unverified=sum(m.coverage.unverified for m in self.machines),
            other=sum(m.coverage.other for m in self.machines),
            empty=sum(m.coverage.empty for m in self.machines),
        )


def layouts_by_board(dataset: Dataset) -> dict[str, Layout]:
    """Every layout, keyed by the board id it draws.

    A board carries at most one map in this dataset, so the last layout
    found for a board id wins; nothing here enforces uniqueness, because
    that is the validator's job, not the view layer's.
    """
    return {layout.board: layout for layout in dataset.layouts.values()}


def machine_view(
    machine: Machine,
    dataset: Dataset,
    *,
    targets: dict[str, tuple[str, str]] | None = None,
    layouts: dict[str, Layout] | None = None,
) -> MachineView:
    if targets is None:
        targets = reference_targets(dataset)
    if layouts is None:
        layouts = layouts_by_board(dataset)
    boards = dataset.boards_for(machine.id)
    kind_counts: dict[str, int] = {}
    for board in boards:
        kind_counts[board.board] = kind_counts.get(board.board, 0) + 1
    views = tuple(
        board_view(
            board,
            dataset,
            disambiguate=kind_counts[board.board] > 1,
            targets=targets,
            layout=layouts.get(board.id),
        )
        for board in boards
    )
    return MachineView(
        id=machine.id,
        name=machine.name,
        family=machine.family,
        family_name=label_for(FAMILY_NAMES, machine.family),
        aliases=machine.aliases,
        notes=machine.notes,
        linked_notes=note_views(machine.notes, targets),
        batteries=machine.batteries,
        url=f"{machine.id}/index.html",
        boards=views,
        coverage=coverage_for(boards),
        hazards=machine_hazards(boards, machine),
    )


def _family_sort_key(family_id: str) -> tuple[int, str]:
    try:
        return (FAMILY_ORDER.index(family_id), family_id)
    except ValueError:
        return (len(FAMILY_ORDER), family_id)


def family_views(machines: list[MachineView]) -> tuple[FamilyView, ...]:
    grouped: dict[str, list[MachineView]] = {}
    for machine in machines:
        grouped.setdefault(machine.family, []).append(machine)
    families = []
    for family_id in sorted(grouped, key=_family_sort_key):
        members = tuple(sorted(grouped[family_id], key=lambda m: natural_key(m.name)))
        families.append(
            FamilyView(
                id=family_id,
                name=label_for(FAMILY_NAMES, family_id),
                machines=members,
            )
        )
    return tuple(families)


# --------------------------------------------------------------------------
# Status page
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenQuestion:
    kind: str
    title: str
    detail: str
    url: str | None = None


@dataclass(frozen=True)
class StatusView:
    coverage: Coverage
    empty_boards: tuple[OpenQuestion, ...] = ()
    unverified_boards: tuple[OpenQuestion, ...] = ()
    derived_boards: tuple[OpenQuestion, ...] = ()
    boards_without_sources: tuple[OpenQuestion, ...] = ()
    positions_without_designators: tuple[OpenQuestion, ...] = ()
    parts_without_offers: tuple[OpenQuestion, ...] = ()

    @property
    def total(self) -> int:
        return sum(
            len(group)
            for group in (
                self.empty_boards,
                self.unverified_boards,
                self.derived_boards,
                self.boards_without_sources,
                self.positions_without_designators,
                self.parts_without_offers,
            )
        )


def status_view(machines: tuple[MachineView, ...], dataset: Dataset) -> StatusView:
    empty: list[OpenQuestion] = []
    unverified: list[OpenQuestion] = []
    derived: list[OpenQuestion] = []
    sourceless: list[OpenQuestion] = []
    designatorless: list[OpenQuestion] = []

    for machine in machines:
        for board in machine.boards:
            where = f"{machine.name} — {board.title}"
            if board.is_empty:
                empty.append(
                    OpenQuestion(
                        "empty",
                        where,
                        "No capacitor list is established for this board.",
                        board.url,
                    )
                )
            if board.verification.status == "unverified":
                unverified.append(
                    OpenQuestion(
                        "unverified",
                        where,
                        "Nothing on this board has been checked against a "
                        "source.",
                        board.url,
                    )
                )
            elif board.verification.status == "derived":
                derived.append(
                    OpenQuestion(
                        "derived",
                        where,
                        "Not confirmed against this board revision.",
                        board.url,
                    )
                )
            if not board.sources:
                sourceless.append(
                    OpenQuestion(
                        "no-sources",
                        where,
                        "The board cites no sources.",
                        board.url,
                    )
                )
            if board.rows_without_designators:
                count = board.rows_without_designators
                noun = "position" if count == 1 else "positions"
                designatorless.append(
                    OpenQuestion(
                        "no-designators",
                        where,
                        f"{count} {noun} without reference designators.",
                        board.url,
                    )
                )

    offered = {part_id for entries in dataset.offers.values() for part_id in entries}
    partless = tuple(
        OpenQuestion(
            "no-offer",
            f"{part.manufacturer} {part.mpn}",
            "No supplier lists a stock number for this part.",
            None,
        )
        for part in sorted(dataset.parts.values(), key=lambda p: p.id)
        if part.id not in offered
    )

    coverage = Coverage(
        verified=sum(m.coverage.verified for m in machines),
        derived=sum(m.coverage.derived for m in machines),
        unverified=sum(m.coverage.unverified for m in machines),
        other=sum(m.coverage.other for m in machines),
        empty=sum(m.coverage.empty for m in machines),
    )
    return StatusView(
        coverage=coverage,
        empty_boards=tuple(empty),
        unverified_boards=tuple(unverified),
        derived_boards=tuple(derived),
        boards_without_sources=tuple(sourceless),
        positions_without_designators=tuple(designatorless),
        parts_without_offers=partless,
    )


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def search_index(machines: tuple[MachineView, ...]) -> list[dict]:
    """Entries for the client-side filter.

    `text` is what the filter matches on; it holds designators and values so
    someone who knows only 'C401' or '3300' can find the board.
    """
    entries: list[dict] = []
    for machine in machines:
        haystack = " ".join((machine.name, *machine.aliases, machine.family_name))
        entries.append(
            {
                "type": "machine",
                "title": machine.name,
                "subtitle": machine.family_name,
                "family": machine.family,
                "url": machine.url,
                "status": machine.coverage.worst,
                "text": haystack.lower(),
            }
        )
        for board in machine.boards:
            words = [machine.name, *machine.aliases, board.title, board.kind_label]
            words.extend(board.revisions)
            for row in board.rows:
                words.extend(row.designators)
                words.append(row.capacitance)
                words.append(row.voltage)
            entries.append(
                {
                    "type": "board",
                    "title": f"{machine.name} — {board.title}",
                    "subtitle": board.verification.label,
                    "family": machine.family,
                    "url": board.url,
                    "status": board.verification.status,
                    "text": " ".join(words).lower(),
                }
            )
    return entries


# --------------------------------------------------------------------------
# The whole site
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CapacitorTypeView:
    """One value of the type enum, for the key on the reference page."""

    id: str
    label: str
    icon_url: str
    polarised: bool


def capacitor_type_views() -> tuple[CapacitorTypeView, ...]:
    return tuple(
        CapacitorTypeView(
            id=type_id,
            label=label,
            icon_url=f"assets/img/cap-{type_id}.svg",
            polarised=type_id in POLARISED_TYPES,
        )
        for type_id, label in CAPACITOR_TYPE_NAMES.items()
    )


@dataclass(frozen=True)
class SiteContext:
    machines: tuple[MachineView, ...]
    families: tuple[FamilyView, ...]
    boards: tuple[BoardView, ...]
    status: StatusView
    series: tuple[SeriesView, ...]
    parts: tuple[PartView, ...]
    coverage: Coverage
    search: list[dict] = field(default_factory=list)

    @property
    def machine_count(self) -> int:
        return len(self.machines)

    @property
    def board_count(self) -> int:
        return len(self.boards)

    @property
    def capacitor_count(self) -> int:
        return sum(board.capacitor_count for board in self.boards)


def build_context(dataset: Dataset) -> SiteContext:
    """Everything the templates need, worked out once."""
    targets = reference_targets(dataset)
    layouts = layouts_by_board(dataset)
    machines = tuple(
        machine_view(machine, dataset, targets=targets, layouts=layouts)
        for machine in sorted(
            dataset.machines.values(), key=lambda m: natural_key(m.name)
        )
    )
    boards = tuple(board for machine in machines for board in machine.boards)
    status = status_view(machines, dataset)
    return SiteContext(
        machines=machines,
        families=family_views(list(machines)),
        boards=boards,
        status=status,
        series=tuple(
            series_view(series)
            for series in sorted(dataset.series.values(), key=lambda s: s.id)
        ),
        parts=tuple(
            _part_view(part, dataset)
            for part in sorted(dataset.parts.values(), key=lambda p: p.id)
        ),
        coverage=status.coverage,
        search=search_index(machines),
    )
