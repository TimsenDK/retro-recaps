"""Tests for `tools.site.layout`, the layout-to-SVG renderer."""

from __future__ import annotations

from collections.abc import Iterable

from tools.model import Layout, LayoutFeature
from tools.site.layout import render_layout


def demo_layout(
    designators: Iterable[str],
    approximate_designators: frozenset[str] = frozenset(),
    anchors: tuple[tuple[str, float, float], ...] = (),
    precision: str = "measured",
) -> Layout:
    """A minimal, self-consistent `Layout` for renderer tests.

    The outline is 1000x620 so the viewBox a test asserts on is the outline
    size verbatim, with no scaling step in between to reason about.
    """
    capacitors = tuple(
        LayoutFeature(
            kind="capacitor",
            x=0.2,
            y=0.3,
            designator=designator,
            approximate=designator in approximate_designators,
        )
        for designator in designators
    )
    anchor_features = tuple(
        LayoutFeature(kind="anchor", x=x, y=y, label=label)
        for label, x, y in anchors
    )
    return Layout(
        id="demo-layout",
        board="demo-board",
        precision=precision,
        verification="verified",
        orientation="component side up",
        width=1000,
        height=620,
        features=capacitors + anchor_features,
    )


def test_every_capacitor_is_drawn_once_with_an_addressable_id() -> None:
    layout = demo_layout(["C1", "C2", "C3"])
    svg = render_layout(layout)
    for designator in ("C1", "C2", "C3"):
        assert svg.count(f'id="pos-{designator}"') == 1
        assert f">{designator}<" in svg


def test_the_drawing_states_its_own_frame_and_nothing_else() -> None:
    layout = demo_layout(["C1"])
    svg = render_layout(layout)
    assert 'viewBox="0 0 1000 620"' in svg
    assert "width=" not in svg.split(">", 1)[0]
    assert "<image" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_an_approximate_position_is_drawn_differently() -> None:
    layout = demo_layout(["C1"], approximate_designators={"C1"})
    svg = render_layout(layout)
    assert 'class="pos approx"' in svg


def test_a_file_level_approximate_precision_marks_every_position() -> None:
    layout = demo_layout(["C1"], precision="approximate")
    svg = render_layout(layout)
    assert 'class="pos approx"' in svg


def test_an_anchor_is_labelled_but_not_addressable() -> None:
    layout = demo_layout(["C1"], anchors=[("Power connector", 0.9, 0.5)])
    svg = render_layout(layout)
    assert ">Power connector<" in svg
    assert 'id="pos-Power' not in svg
