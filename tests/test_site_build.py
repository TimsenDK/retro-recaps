"""Rendering, and the one thing worth asserting about the real dataset.

These tests check that the right files land in the right places and that a
board page carries the load-bearing facts — the designators, the verification
status, the safety link. They deliberately do not assert on markup beyond
that: a test that breaks when a class name changes costs more than it catches.
"""

from __future__ import annotations

import json
import re
import shutil
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
        assets=ROOT / "site" / "assets",
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
    body = page.split("<body", 1)[1]
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


# --------------------------------------------------------------------------
# The battery reaches the sheet that gets printed
# --------------------------------------------------------------------------


def test_a_mainboard_page_prints_the_machines_battery(tmp_path: Path) -> None:
    """`batteries` is machine-level, but the cell is soldered to this board."""
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "mainboard-rev6a.html").read_text(encoding="utf-8")
    assert "Battery" in page
    assert "NICD" in page
    assert "no-print" not in page.split('class="battery"')[1].split("</section>")[0]


def test_a_psu_page_does_not_print_a_battery_panel(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "psu.html").read_text(encoding="utf-8")
    assert 'class="battery"' not in page


def test_the_machine_page_still_prints_its_battery(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "index.html").read_text(encoding="utf-8")
    assert 'class="battery"' in page


# --------------------------------------------------------------------------
# Cross-file references in notes become links
# --------------------------------------------------------------------------


def test_a_note_reference_renders_as_a_working_link(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "mainboard-rev6a.html").read_text(encoding="utf-8")
    assert '<a href="../amiga-500/psu.html">' in page
    assert "psu.yaml" not in page.split("<h2>Notes on this board</h2>")[1]


def test_a_note_reference_link_target_exists(tmp_path: Path) -> None:
    """A relative href from a board page must resolve to a written file."""
    out = build_fixture(tmp_path)
    assert (out / "amiga-500" / "psu.html").is_file()


# --------------------------------------------------------------------------
# The print stylesheet
# --------------------------------------------------------------------------


def print_block(tmp_path: Path) -> str:
    out = build_fixture(tmp_path)
    page = (out / "amiga-500" / "psu.html").read_text(encoding="utf-8")
    return page.split("@media print", 1)[1]


def test_hazard_panels_survive_the_print_stylesheet(tmp_path: Path) -> None:
    """Two panels can land on one board page; both must print bordered."""
    block = print_block(tmp_path)
    rules = block.split("page-break-inside:avoid", 1)[0]
    assert ".hazard" in rules
    assert ".battery" in rules
    assert "2px solid #000" in block


def test_the_print_stylesheet_never_hides_a_hazard(tmp_path: Path) -> None:
    block = print_block(tmp_path)
    hidden = block.split("display:none", 1)[0]
    assert ".hazard" not in hidden
    assert ".battery" not in hidden


# --------------------------------------------------------------------------
# The output directory does not accumulate pages that no longer exist
# --------------------------------------------------------------------------


def build_into(out: Path, data: Path, assets: Path | None = None) -> None:
    from tools.loader import load_dataset
    from tools.site.build import render_site
    from tools.site.context import build_context

    dataset, _ = load_dataset(data)
    render_site(
        build_context(dataset),
        root=data,
        out=out,
        templates=ROOT / "site" / "templates",
        static=ROOT / "site" / "static",
        assets=assets if assets is not None else ROOT / "site" / "assets",
    )


def copied_fixture(tmp_path: Path) -> Path:
    data = tmp_path / "src"
    shutil.copytree(FIXTURES / "site", data)
    return data


def test_a_deleted_board_takes_its_page_with_it(tmp_path: Path) -> None:
    """A stale page is worse than a missing one: it still lists parts."""
    data = copied_fixture(tmp_path)
    out = tmp_path / "build"
    build_into(out, data)
    assert (out / "amiga-500" / "psu.html").is_file()

    (data / "data" / "amiga-500" / "psu.yaml").unlink()
    build_into(out, data)
    assert not (out / "amiga-500" / "psu.html").exists()
    assert not (out / "amiga-500" / "psu.yaml").exists()
    assert not (out / "amiga-500" / "psu.json").exists()
    assert (out / "amiga-500" / "mainboard-rev6a.html").is_file()


def test_a_deleted_machine_takes_its_directory_with_it(tmp_path: Path) -> None:
    data = copied_fixture(tmp_path)
    out = tmp_path / "build"
    build_into(out, data)
    assert (out / "mac-se").is_dir()

    shutil.rmtree(data / "data" / "mac-se")
    build_into(out, data)
    assert not (out / "mac-se").exists()


def test_pruning_leaves_files_the_generator_did_not_write(tmp_path: Path) -> None:
    """It removes what the last build wrote, not whatever it finds."""
    data = copied_fixture(tmp_path)
    out = tmp_path / "build"
    build_into(out, data)
    stranger = out / "CNAME"
    stranger.write_text("example.invalid\n", encoding="utf-8")
    build_into(out, data)
    assert stranger.is_file()


def test_a_second_build_of_an_unchanged_dataset_removes_nothing(
    tmp_path: Path,
) -> None:
    data = copied_fixture(tmp_path)
    out = tmp_path / "build"
    build_into(out, data)
    before = sorted(path.relative_to(out).as_posix() for path in out.rglob("*"))
    build_into(out, data)
    after = sorted(path.relative_to(out).as_posix() for path in out.rglob("*"))
    assert before == after


# --------------------------------------------------------------------------
# Static assets and the fonts they carry
# --------------------------------------------------------------------------

ASSETS = ROOT / "site" / "assets"

FONT_URL = re.compile(r'url\("([^"]+\.woff2)"\)')


def test_the_assets_directory_is_copied_verbatim(tmp_path: Path) -> None:
    """Subdirectories and bytes both survive the copy."""
    out = build_fixture(tmp_path)
    for source in ASSETS.rglob("*"):
        if not source.is_file():
            continue
        target = out / "assets" / source.relative_to(ASSETS)
        assert target.is_file(), target
        assert target.read_bytes() == source.read_bytes(), target


def test_a_removed_asset_does_not_survive_in_the_output(tmp_path: Path) -> None:
    data = copied_fixture(tmp_path)
    assets = tmp_path / "assets"
    (assets / "img").mkdir(parents=True)
    (assets / "img" / "diagram.svg").write_text("<svg/>", encoding="utf-8")
    out = tmp_path / "build"
    build_into(out, data, assets=assets)
    assert (out / "assets" / "img" / "diagram.svg").is_file()

    (assets / "img" / "diagram.svg").unlink()
    build_into(out, data, assets=assets)
    assert not (out / "assets" / "img" / "diagram.svg").exists()
    assert not (out / "assets" / "img").exists()


def test_every_font_url_resolves_from_the_page_that_asks_for_it(
    tmp_path: Path,
) -> None:
    """The sheet is inlined, so its URLs are relative to the page, not to a
    stylesheet. A page one directory down needs a different prefix from the
    front page, and both must land on a real file."""
    out = build_fixture(tmp_path)
    checked = 0
    for page in out.rglob("*.html"):
        urls = set(FONT_URL.findall(page.read_text(encoding="utf-8")))
        assert urls, page
        for url in urls:
            assert (page.parent / url).is_file(), f"{page}: {url}"
            checked += 1
    assert checked > 0


def test_the_fonts_are_files_and_not_embedded_in_the_stylesheet(
    tmp_path: Path,
) -> None:
    """Inlined into ninety pages, a base64 font would be paid for ninety
    times."""
    out = build_fixture(tmp_path)
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert ";base64," not in text, page
        assert "url(data:" not in text, page
        assert 'url("data:' not in text, page
        assert "font-display:swap" in text, page


def test_each_font_family_ships_its_licence(tmp_path: Path) -> None:
    out = build_fixture(tmp_path)
    for licence in ("ChakraPetch-OFL.txt", "IBMPlex-OFL.txt"):
        text = (out / "assets" / "fonts" / licence).read_text(encoding="utf-8")
        assert "SIL Open Font License" in text


def test_no_bitmap_face_is_wired_as_the_display_face(tmp_path: Path) -> None:
    """The heading face has to survive a 600 dpi printer.

    It was Silkscreen, which does not: a bitmap face set at 10 pt prints as
    a row of grey smudges, so print had to override it back to the text
    face. Chakra Petch is an ordinary outline face, so the printed sheet
    now keeps the site's own headings — but that only holds while the
    display face is not a bitmap one again.
    """
    out = build_fixture(tmp_path)
    sheet = (out / "index.html").read_text(encoding="utf-8").split("<style>", 1)[1]
    display = sheet.split("--display:", 1)[1].split(";", 1)[0]
    for bitmap in ("Silkscreen", "Press Start 2P", "Departure Mono", "VT323"):
        assert bitmap not in display, (
            f"{bitmap} is a bitmap face; if it is wired as --display, print "
            f"must override it back to the text face"
        )
    assert "Chakra Petch" in display
    assert "IBM Plex Sans" in display, "the fallback must still be the body sans"


def test_the_display_face_never_reaches_the_body_or_a_hazard(
    tmp_path: Path,
) -> None:
    out = build_fixture(tmp_path)
    sheet = (out / "index.html").read_text(encoding="utf-8").split("<style>", 1)[1]
    body = sheet.split("body{", 1)[1].split("}", 1)[0]
    assert "--display" not in body
    hazard = re.search(r"\.hazard h2,[^{]*\{([^}]*font-family[^}]*)\}", sheet)
    assert hazard is not None
    assert "var(--sans)" in hazard.group(1)
