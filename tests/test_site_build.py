"""Rendering, and the one thing worth asserting about the real dataset.

These tests check that the right files land in the right places and that a
board page carries the load-bearing facts — the designators, the verification
status, the safety link. They deliberately do not assert on markup beyond
that: a test that breaks when a class name changes costs more than it catches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import cli
from tools.site.build import build_site

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def build_fixture(tmp_path: Path) -> Path:
    """Render the site fixture, using the repository's real templates."""
    out = tmp_path / "build"
    from tools.loader import load_dataset
    from tools.site.build import render_site
    from tools.site.context import build_context

    dataset, issues = load_dataset(FIXTURES / "site")
    assert issues == []
    render_site(
        build_context(dataset),
        root=FIXTURES / "site",
        out=out,
        templates=ROOT / "site" / "templates",
        static=ROOT / "site" / "static",
    )
    return out


def test_build_site_command_is_registered() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["build-site", "--help"])
    assert exc.value.code == 0


def test_every_page_type_is_written(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    for relative in (
        "index.html",
        "reference.html",
        "safety.html",
        "status.html",
        "search-index.json",
        "search.js",
        "amiga-500/index.html",
        "amiga-500/mainboard-rev6a.html",
        "amiga-500/psu.html",
        "mac-se/logic.html",
    ):
        assert (out / relative).is_file(), relative


def test_each_board_gets_its_data_alongside_its_page(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    assert (out / "amiga-500" / "mainboard-rev6a.yaml").is_file()
    document = json.loads(
        (out / "amiga-500" / "mainboard-rev6a.json").read_text(encoding="utf-8")
    )
    assert document["id"] == "amiga-500-mainboard-rev6a"


def test_a_board_page_carries_its_designators_and_values(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "mainboard-rev6a.html").read_text(encoding="utf-8")
    assert "C321" in page
    assert "C8" in page
    assert "47 µF" in page
    assert "was 16 V" in page


def test_a_derived_board_states_the_caution_in_words(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "mac-se" / "logic.html").read_text(encoding="utf-8")
    body = page.split("<body>", 1)[1]
    assert "tone-caution" in body
    assert "tone-verified" not in body
    assert "Nobody has confirmed this list" in body


def test_an_empty_board_renders_the_open_question(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "psu.html").read_text(encoding="utf-8")
    assert "Open question" in page
    assert "<tbody>" not in page


def test_a_psu_page_links_to_safety(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "psu.html").read_text(encoding="utf-8")
    assert "Mains voltage" in page
    assert '../safety.html' in page


def test_pages_are_self_contained(tmp_path: Path) -> None:
    """No CDN, no web font, no external stylesheet — it must work offline."""
    out = build_fixture(tmp_path)
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert "<link" not in text, page
        assert "@import" not in text, page
        assert 'src="http' not in text, page
        assert "fonts.googleapis" not in text, page


def test_search_index_is_valid_json_and_has_a_js_twin(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    entries = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    assert any(entry["type"] == "board" for entry in entries)
    js = (out / "search-index.js").read_text(encoding="utf-8")
    assert js.startswith("window.RETRO_SEARCH = ")


def test_the_real_dataset_builds(tmp_path: Path) -> None:
    """A smoke test over `data/`, which the fixtures cannot stand in for."""
    out = tmp_path / "build"
    written = build_site(ROOT, out)
    assert (out / "index.html").is_file()
    assert (out / "status.html").is_file()
    assert (out / "safety.html").is_file()

    pages = [path for path in written if path.suffix == ".html"]
    assert len(pages) > 20

    board = out / "amiga-500" / "mainboard-rev6a.html"
    assert board.is_file()
    text = board.read_text(encoding="utf-8")
    assert "C401" in text
    assert "Verified" in text
    assert (out / "amiga-500" / "mainboard-rev6a.yaml").is_file()
