"""Machine photographs and the credit each one legally requires.

The photographs are not ours. They come from Wikimedia Commons under CC0,
CC BY, CC BY-SA or a public-domain dedication, and the BY and BY-SA files
oblige us to name the photographer wherever the image is shown. That
obligation is the reason this module exists: an image is only offered to a
template together with the credit line it must be rendered with, so there is
no way to place a photograph on a page and forget the attribution.

`site/assets/img/machines/images.yaml` is the record. A machine absent from it
simply has no photograph, which is a state the site handles rather than a
build failure — one machine in the set has no acceptably licensed picture.

Pixel dimensions are read from the JPEG itself rather than trusted to the YAML.
They are written into the markup so the page reserves the right box before the
image arrives and nothing below it jumps.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import yaml

IMAGES_FILE = "img/machines/images.yaml"
"""Relative to `site/assets/`."""

_PUBLIC_DOMAIN = "public domain"

_SOF_MARKERS = frozenset(
    # SOF0..SOF15, minus the four that are not frame headers.
    set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
)


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of a JPEG, or None if the file is not readable as one.

    Just enough of the format to walk the marker segments to the frame
    header. The site ships eighteen JPEGs; adding a dependency to measure
    them would cost more than parsing them.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return None
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker in (0xFF, 0x01) or 0xD0 <= marker <= 0xD9:
            offset += 2
            continue
        (length,) = struct.unpack(">H", data[offset + 2 : offset + 4])
        if length < 2:
            return None
        if marker in _SOF_MARKERS:
            if offset + 9 > len(data):
                return None
            height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
            return (width, height) if width and height else None
        offset += 2 + length
    return None


@dataclass(frozen=True)
class PhotoView:
    """One machine photograph, with everything needed to publish it lawfully."""

    machine_id: str
    machine_name: str
    url: str
    """Relative to the site's `assets/` directory, like every other asset."""
    card_url: str
    author: str
    licence: str
    licence_url: str
    source_url: str
    width: int | None = None
    height: int | None = None
    card_width: int | None = None
    card_height: int | None = None

    @property
    def alt(self) -> str:
        """Alt text describing the subject, not the file.

        The credit is rendered as visible text beside the image, so it does
        not belong here as well — a screen reader would read the machine name
        twice and the photographer twice.
        """
        return f"{self.machine_name}, photographed from the front."

    @property
    def is_public_domain(self) -> bool:
        return not self.licence_url or _PUBLIC_DOMAIN in self.licence.lower()

    @property
    def requires_attribution(self) -> bool:
        """Whether the licence obliges us to name the photographer.

        Public-domain files do not, and are credited anyway — but the answer
        is recorded so a test can assert the obligation is met where it
        exists rather than assert on politeness.
        """
        return not self.is_public_domain

    @property
    def aspect_ratio(self) -> str | None:
        if not self.width or not self.height:
            return None
        return f"{self.width} / {self.height}"


def load_photos(
    assets: Path, names: dict[str, str] | None = None
) -> dict[str, PhotoView]:
    """Every photograph the site may use, keyed by machine id.

    `names` maps machine id to display name, for alt text. An id the caller
    does not name falls back to the id, the same way the rest of the site
    treats an unknown id.
    """
    names = names or {}
    path = assets / IMAGES_FILE
    if not path.is_file():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = document.get("machines") or {}
    directory = path.parent
    photos: dict[str, PhotoView] = {}
    for machine_id, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        file = entry.get("file")
        author = entry.get("author")
        licence = entry.get("licence")
        if not file or not author or not licence:
            # A half-recorded image is one we cannot credit, so it is one we
            # do not publish.
            continue
        card = entry.get("card") or file
        full_size = jpeg_size(directory / file)
        card_size = jpeg_size(directory / card)
        photos[machine_id] = PhotoView(
            machine_id=machine_id,
            machine_name=names.get(machine_id, machine_id),
            url=f"img/machines/{file}",
            card_url=f"img/machines/{card}",
            author=str(author),
            licence=str(licence),
            licence_url=str(entry.get("licence_url") or ""),
            source_url=str(entry.get("source_url") or ""),
            width=full_size[0] if full_size else None,
            height=full_size[1] if full_size else None,
            card_width=card_size[0] if card_size else None,
            card_height=card_size[1] if card_size else None,
        )
    return photos
