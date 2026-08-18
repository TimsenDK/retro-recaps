"""A labelled grid overlay for reading capacitor positions off a scan.

Not part of the site build, and never run by it — the same standing as
`tools.cartoonify`. It exists so a person can put a reference picture (a
board-layout drawing, a photograph) in `.photo-cache/`, draw a numbered grid
over it, and read off which cell each designator falls in by eye, cropping any
cell that is hard to read at full size. Needs the `images` extra:

    python -m pip install -e ".[images]"
    python -m tools.gridref --source .photo-cache/board.png --out .photo-cache/grid.png

The coordinates it helps a person read are never computed by this module —
they are recorded by hand into a layout YAML file, to two decimal places.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

COLUMN_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

GRID_INK = (255, 0, 0)
"""Red, because the reference pictures are grey-green boards and beige cases."""


def _cell(size: tuple[int, int], columns: int, rows: int) -> tuple[float, float]:
    return size[0] / columns, size[1] / rows


def grid_overlay(source: Path, out: Path, columns: int = 20, rows: int = 20) -> Path:
    """A copy of the reference picture with a labelled grid drawn over it."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = _cell(image.size, columns, rows)
    for index in range(1, columns):
        x = index * width
        draw.line(((x, 0), (x, image.height)), fill=GRID_INK, width=1)
    for index in range(1, rows):
        y = index * height
        draw.line(((0, y), (image.width, y)), fill=GRID_INK, width=1)
    for column in range(columns):
        for row in range(rows):
            draw.text(
                (column * width + 2, row * height + 2),
                f"{COLUMN_LABELS[column % 26]}{row + 1}",
                fill=GRID_INK,
            )
    image.save(out)
    return out


def crop(
    source: Path,
    out: Path,
    column: int,
    row: int,
    columns: int = 20,
    rows: int = 20,
    margin: float = 0.5,
) -> Path:
    """One cell of the grid, plus `margin` cells of context on every side."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = _cell(image.size, columns, rows)
    left = max(0, round((column - margin) * width))
    top = max(0, round((row - margin) * height))
    right = min(image.width, round((column + 1 + margin) * width))
    bottom = min(image.height, round((row + 1 + margin) * height))
    image.crop((left, top, right, bottom)).save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=20)
    parser.add_argument("--rows", type=int, default=20)
    args = parser.parse_args(argv)
    written = grid_overlay(args.source, args.out, columns=args.columns, rows=args.rows)
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
