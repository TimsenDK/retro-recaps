"""A board layout drawn as inline SVG.

A layout file only ever records where things are, not how to draw them: the
same normalised coordinates should describe a board whether it is shown at
the size of a thumbnail or filling a page, and neither the dataset nor its
validator has any business knowing what a circle looks like. That drawing
decision lives here, in one place, so a template never touches an `x` or a
`y` directly and the markup for "this position is not certain" is written
exactly once.

The output is inlined into the page rather than linked as a file, because a
linked image cannot be styled from the site's own stylesheet or take the
page's currentColor into light mode, dark mode and print the way the rest of
the hand-drawn diagrams do (see `site/assets/img/polarity.svg`). Inlining
also means the drawing can carry ids a stylesheet or a later script can
target, which a `<img src=...>` never could.
"""

from __future__ import annotations

from dataclasses import dataclass

from markupsafe import Markup, escape

from tools.model import Layout, LayoutFeature

_OUTLINE_RADIUS_FRACTION = 0.02
"""Corner radius of the board outline, as a fraction of its width."""

_CAPACITOR_RADIUS_FRACTION = 0.018
"""Radius of a capacitor marker, as a fraction of the board width."""

_ANCHOR_SIZE_FRACTION = 0.024
"""Side length of an anchor marker, as a fraction of the board width."""

_LABEL_OFFSET_FRACTION = 0.03
"""How far below its marker a label sits, as a fraction of the board width."""


@dataclass(frozen=True)
class LayoutView:
    """A layout, rendered and ready to drop into a page.

    `precision` and `is_approximate` are surfaced separately from the SVG
    itself so a template can caption the drawing ("measured", "approximate
    position") without parsing markup to find out which it got.
    """

    svg: Markup
    precision: str
    is_approximate: bool
    orientation: str
    notes: tuple[str, ...]


def _is_approximate(layout: Layout) -> bool:
    """A layout reads as approximate if it says so, or if any part of it does.

    A single feature is allowed to be less certain than the file it lives
    in — one part measured off a blurry photo in an otherwise-measured set —
    but never more certain than the file, so the file's own precision is the
    floor.
    """
    if layout.precision == "approximate":
        return True
    return any(feature.approximate for feature in layout.features)


def _capacitor_markup(
    feature: LayoutFeature,
    cx: float,
    cy: float,
    radius: float,
    label_y: float,
    layout_approximate: bool,
) -> str:
    designator = escape(feature.designator or "")
    # A layout marked approximate as a whole is a floor, not a default: it
    # must show through even on a feature that never set its own flag.
    approximate = feature.approximate or layout_approximate
    classes = "pos approx" if approximate else "pos"
    # The dashed ring is drawn by `.pos.approx circle` in the stylesheet,
    # which is author CSS and so always wins over an SVG presentation
    # attribute; an inline stroke-dasharray here would be dead weight,
    # not a fallback.
    return (
        f'<g class="{classes}" id="pos-{designator}">'
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" '
        f'fill="none" stroke="currentColor"/>'
        f'<text x="{cx:.2f}" y="{label_y:.2f}" text-anchor="middle">'
        f"{designator}</text>"
        f"</g>"
    )


def _anchor_markup(
    feature: LayoutFeature, cx: float, cy: float, size: float, label_y: float
) -> str:
    label = escape(feature.label or "")
    half = size / 2
    return (
        f'<g class="anchor">'
        f'<rect x="{cx - half:.2f}" y="{cy - half:.2f}" '
        f'width="{size:.2f}" height="{size:.2f}" '
        f'fill="none" stroke="currentColor"/>'
        f'<text x="{cx:.2f}" y="{label_y:.2f}" text-anchor="middle">'
        f"{label}</text>"
        f"</g>"
    )


def render_layout(layout: Layout) -> str:
    """Draw a layout as a self-contained SVG document.

    Coordinates are normalised in the source data, so every position is
    scaled by the outline's own width and height here — the one place that
    conversion needs to happen.
    """
    width, height = layout.width, layout.height
    corner_radius = width * _OUTLINE_RADIUS_FRACTION
    capacitor_radius = width * _CAPACITOR_RADIUS_FRACTION
    anchor_size = width * _ANCHOR_SIZE_FRACTION
    label_offset = width * _LABEL_OFFSET_FRACTION
    title = escape(layout.board)
    layout_approximate = layout.precision == "approximate"

    parts: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width:g} {height:g}" role="img">',
        f"<title>{title}</title>",
        f'<rect x="0" y="0" width="{width:g}" height="{height:g}" '
        f'rx="{corner_radius:.2f}" fill="none" stroke="currentColor"/>',
    ]
    for feature in layout.features:
        cx = feature.x * width
        cy = feature.y * height
        if feature.kind == "capacitor":
            label_y = cy + capacitor_radius + label_offset
            parts.append(
                _capacitor_markup(
                    feature, cx, cy, capacitor_radius, label_y, layout_approximate
                )
            )
        elif feature.kind == "anchor":
            label_y = cy + anchor_size / 2 + label_offset
            parts.append(_anchor_markup(feature, cx, cy, anchor_size, label_y))
    parts.append("</svg>")
    return "".join(parts)


def layout_view(layout: Layout) -> LayoutView:
    """Build the view a template renders, marking the SVG safe exactly once."""
    return LayoutView(
        svg=Markup(render_layout(layout)),
        precision=layout.precision,
        is_approximate=_is_approximate(layout),
        orientation=layout.orientation,
        notes=layout.notes,
    )
