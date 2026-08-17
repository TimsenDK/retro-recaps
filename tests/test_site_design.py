"""The visual layer: photograph credits, family accents, symbols, polarity.

The photograph tests are the load-bearing ones. CC BY and CC BY-SA oblige the
site to name the photographer wherever the image is shown, so "the credit is
rendered" is a licence condition and not a matter of taste. The contrast tests
are the other kind of obligation: the family accents are computed against the
backgrounds they actually sit on rather than judged by eye.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.loader import load_dataset
from tools.model import Board, Capacitor, Dataset
from tools.site.build import compact_css, render_site
from tools.site.context import (
    CAPACITOR_TYPE_NAMES,
    POLARISED_TYPES,
    board_view,
    build_context,
    capacitor_type_views,
    family_mark,
)
from tools.site.images import jpeg_size, load_photos

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
ASSETS = ROOT / "site" / "assets"


@pytest.fixture(scope="module")
def site_out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("design")
    dataset, issues = load_dataset(FIXTURES / "site")
    assert issues == []
    render_site(
        build_context(dataset),
        root=FIXTURES / "site",
        out=out,
        templates=ROOT / "site" / "templates",
        static=ROOT / "site" / "static",
        assets=ASSETS,
    )
    return out


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    loaded, issues = load_dataset(FIXTURES / "site")
    assert issues == []
    return loaded


def read(out: Path, relative: str) -> str:
    return (out / relative).read_text(encoding="utf-8")


def stylesheet(out: Path) -> str:
    return read(out, "index.html").split("<style>", 1)[1].split("</style>", 1)[0]


# --------------------------------------------------------------------------
# Photographs, and the credit their licence requires
# --------------------------------------------------------------------------


def test_the_recorded_photographs_are_all_readable_and_measurable() -> None:
    photos = load_photos(ASSETS)
    assert photos, "images.yaml records no photographs"
    for photo in photos.values():
        assert (ASSETS / "img" / "machines").joinpath(
            Path(photo.url).name
        ).is_file(), photo.machine_id
        assert photo.width and photo.height, photo.machine_id
        assert photo.card_width and photo.card_height, photo.machine_id


def test_every_photograph_names_its_photographer_and_licence() -> None:
    for photo in load_photos(ASSETS).values():
        assert photo.author, photo.machine_id
        assert photo.licence, photo.machine_id
        if photo.requires_attribution:
            assert photo.licence_url, photo.machine_id
            assert photo.source_url, photo.machine_id


def test_an_entry_that_cannot_be_credited_is_not_published(tmp_path: Path) -> None:
    """A photograph without a photographer is one we may not lawfully show."""
    machines = tmp_path / "img" / "machines"
    machines.mkdir(parents=True)
    (machines / "images.yaml").write_text(
        "machines:\n"
        "  good:\n"
        "    file: a.jpg\n"
        "    author: Someone\n"
        "    licence: CC BY 4.0\n"
        "  nameless:\n"
        "    file: b.jpg\n"
        "    licence: CC BY 4.0\n",
        encoding="utf-8",
    )
    photos = load_photos(tmp_path)
    assert set(photos) == {"good"}


def test_a_machine_page_carries_the_credit_beside_its_photograph(
    site_out: Path,
) -> None:
    photos = load_photos(ASSETS)
    photo = photos["amiga-500"]
    page = read(site_out, "amiga-500/index.html")
    assert photo.url in page
    assert photo.author in page
    assert photo.licence in page
    assert photo.licence_url in page
    assert photo.source_url in page


def test_the_index_credits_the_photographer_of_every_card_it_shows(
    site_out: Path,
) -> None:
    """A thumbnail is a use of the image, so it carries the same obligation."""
    page = read(site_out, "index.html")
    shown = [
        photo
        for photo in load_photos(ASSETS).values()
        if photo.card_url in page
    ]
    assert shown, "the index shows no photographs at all"
    for photo in shown:
        assert photo.author in page, photo.machine_id
        assert photo.licence in page, photo.machine_id
        if photo.requires_attribution:
            assert photo.licence_url in page, photo.machine_id


def test_a_photograph_reserves_its_box_before_it_loads(site_out: Path) -> None:
    photo = load_photos(ASSETS)["amiga-500"]
    page = read(site_out, "amiga-500/index.html")
    tag = re.search(r"<img[^>]*" + re.escape(photo.url) + r"[^>]*>", page)
    assert tag is not None
    markup = tag.group(0)
    assert f'width="{photo.width}"' in markup
    assert f'height="{photo.height}"' in markup
    assert 'loading="lazy"' in markup


def test_a_photograph_has_alt_text_that_describes_the_machine(
    site_out: Path,
) -> None:
    page = read(site_out, "amiga-500/index.html")
    tag = re.search(r'<img[^>]*machines/amiga-500\.jpg[^>]*>', page)
    assert tag is not None
    alt = re.search(r'alt="([^"]*)"', tag.group(0))
    assert alt is not None
    assert "Amiga 500" in alt.group(1)


def test_a_machine_with_no_photograph_still_renders_its_frame(
    site_out: Path,
) -> None:
    """One machine in the set has no acceptably licensed picture."""
    page = read(site_out, "mac-se/index.html")
    assert "machines/mac-se.jpg" in page

    photoless = render_photoless(site_out)
    assert "No freely licensed photograph" in photoless
    assert 'class="shot"' in photoless
    assert "machines/" not in photoless


def render_photoless(site_out: Path) -> str:
    """The Amiga 500 page as it would render with no photograph recorded.

    The fixture dataset holds machines the real site has pictures of, so the
    empty case is exercised by building one page without them rather than by
    depending on which machine happens to be missing one.
    """
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

    dataset, _ = load_dataset(FIXTURES / "site")
    context = build_context(dataset)
    machine = next(m for m in context.machines if m.id == "amiga-500")
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "site" / "templates")),
        autoescape=select_autoescape(["html", "html.j2"], default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("machine.html.j2").render(
        base="../",
        site=context,
        site_name="Retro Recaps",
        site_tagline="",
        site_url="",
        contribute_url="",
        stylesheet="",
        machine=machine,
        photo=None,
    )


def test_jpeg_size_reads_the_real_files() -> None:
    path = ASSETS / "img" / "machines" / "amiga-500-card.jpg"
    size = jpeg_size(path)
    assert size is not None
    assert max(size) == 480


def test_jpeg_size_declines_what_is_not_a_jpeg(tmp_path: Path) -> None:
    path = tmp_path / "not.jpg"
    path.write_bytes(b"<svg/>")
    assert jpeg_size(path) is None
    assert jpeg_size(tmp_path / "absent.jpg") is None


# --------------------------------------------------------------------------
# Capacitor type symbols
# --------------------------------------------------------------------------


def test_every_capacitor_type_has_a_symbol_on_disk() -> None:
    for view in capacitor_type_views():
        assert (ROOT / "site" / view.icon_url).is_file(), view.id


def test_the_symbol_never_appears_without_the_written_type(
    site_out: Path,
) -> None:
    """X2 and Y2 are not interchangeable and their lettering is not legible
    at this size; the words are what carry the meaning."""
    page = read(site_out, "amiga-500/mainboard-rev6a.html")
    cells = re.findall(r'<span class="captype">(.*?)</span>\s*</td>', page, re.S)
    assert cells
    for cell in cells:
        text = re.sub(r"<[^>]+>", "", cell).strip()
        assert text, cell
        assert text in CAPACITOR_TYPE_NAMES.values(), text


def test_a_type_the_site_cannot_name_gets_no_symbol(dataset: Dataset) -> None:
    board = Board(
        id="amiga-500-mainboard-rev3",
        machine="amiga-500",
        board="mainboard",
        revisions=("3",),
        verification="derived",
        capacitors=(
            Capacitor(
                type="something-new",
                capacitance_uf=10,
                voltage_v=16,
                quantity=1,
                designators=("C1",),
            ),
        ),
    )
    row = board_view(board, dataset, disambiguate=False).rows[0]
    assert row.icon_url is None
    assert row.type_label == "something-new"


# --------------------------------------------------------------------------
# Polarity
# --------------------------------------------------------------------------


def polarised_board(types: tuple[str, ...]) -> Board:
    return Board(
        id="amiga-500-mainboard-rev3",
        machine="amiga-500",
        board="mainboard",
        revisions=("3",),
        verification="derived",
        capacitors=tuple(
            Capacitor(
                type=type_id,
                capacitance_uf=10,
                voltage_v=16,
                quantity=1,
                designators=(f"C{index + 1}",),
            )
            for index, type_id in enumerate(types)
        ),
    )


def test_a_board_of_film_and_ceramic_needs_no_polarity_diagram(
    dataset: Dataset,
) -> None:
    view = board_view(
        polarised_board(("film", "film-x2", "ceramic", "bipolar")),
        dataset,
        disambiguate=False,
    )
    assert view.has_polarised is False


def test_one_polarised_position_is_enough(dataset: Dataset) -> None:
    view = board_view(
        polarised_board(("film", "tantalum")), dataset, disambiguate=False
    )
    assert view.has_polarised is True


def test_polarised_types_are_a_subset_of_the_type_enum() -> None:
    assert POLARISED_TYPES < set(CAPACITOR_TYPE_NAMES)


def test_a_board_page_with_electrolytics_carries_the_diagram(
    site_out: Path,
) -> None:
    page = read(site_out, "amiga-500/mainboard-rev6a.html")
    assert 'class="polarity"' in page
    # Inlined, not referenced: only inline markup paints in `currentColor`
    # and therefore reaches paper as black line art.
    assert "<svg" in page
    assert "polarity.svg" not in page


def test_the_reference_page_carries_the_diagram_and_the_symbol_key(
    site_out: Path,
) -> None:
    page = read(site_out, "reference.html")
    assert 'class="polarity"' in page
    for view in capacitor_type_views():
        assert view.icon_url in page
        assert view.label in page


def test_the_polarity_diagram_survives_the_print_stylesheet(
    site_out: Path,
) -> None:
    sheet = stylesheet(site_out)
    printed = sheet.split("@media print", 1)[1]
    assert ".polarity" in printed
    hidden = re.findall(r"([^{}]*)\{[^{}]*display:none[^{}]*\}", printed)
    for selectors in hidden:
        assert ".polarity" not in selectors
        assert ".hazard" not in selectors


def test_photographs_and_decoration_come_off_the_printed_sheet(
    site_out: Path,
) -> None:
    printed = stylesheet(site_out).split("@media print", 1)[1]
    hidden = " ".join(
        re.findall(r"([^{}]*)\{[^{}]*display:none[^{}]*\}", printed)
    )
    for selector in (".shot", ".motif", ".captype img"):
        assert selector in hidden, selector


# --------------------------------------------------------------------------
# Family accents
# --------------------------------------------------------------------------


def relative_luminance(colour: str) -> float:
    value = colour.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    a, b = relative_luminance(first), relative_luminance(second)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def test_the_contrast_helper_agrees_with_the_known_extremes() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast("#777777", "#777777") == pytest.approx(1.0, abs=0.01)


def tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z-]+):\s*(#[0-9a-f]{3,8})", block))


def theme_blocks(sheet: str) -> tuple[str, str]:
    """The light sheet and the dark override, as raw text."""
    dark_start = sheet.index("@media (prefers-color-scheme:dark)")
    dark_end = sheet.index("@media print")
    return sheet[:dark_start], sheet[dark_start:dark_end]


FAMILIES = ("amiga", "commodore-8bit", "commodore-drive", "macintosh")


def test_every_family_accent_passes_aa_in_both_themes(site_out: Path) -> None:
    sheet = stylesheet(site_out)
    light, dark = theme_blocks(sheet)
    for theme, block in (("light", light), (("dark"), dark)):
        base = tokens(block.split(".fam-", 1)[0])
        if theme == "dark":
            # The dark block redefines only what changes; the rest of the
            # palette is inherited from the light one.
            base = {**tokens(light.split(".fam-", 1)[0]), **base}
        grounds = [base["--page"], base["--panel"], base["--panel-alt"]]
        for family in FAMILIES:
            rule = re.search(
                r"\.fam-" + re.escape(family) + r"\{([^}]*)\}", block
            )
            assert rule is not None, f"{theme}/{family}"
            values = tokens(rule.group(1))
            ink = values["--family-ink"]
            chip = values["--family-chip"]
            for ground in grounds + [chip]:
                ratio = contrast(ink, ground)
                where = f"{theme}/{family}: {ink} on {ground}"
                assert ratio >= 4.5, f"{where} = {ratio:.2f}"


def test_a_family_accent_is_never_one_of_the_status_tones(site_out: Path) -> None:
    """A reader must not be able to mistake a family for a verdict."""
    sheet = stylesheet(site_out)
    light, dark = theme_blocks(sheet)
    for block in (light, dark):
        semantic = {
            value
            for name, value in tokens(block.split(".fam-", 1)[0]).items()
            if name.startswith(("--ok-", "--caution-", "--warn-"))
        }
        for family in FAMILIES:
            rule = re.search(r"\.fam-" + re.escape(family) + r"\{([^}]*)\}", block)
            if rule is None:
                continue
            assert not semantic & set(tokens(rule.group(1)).values()), family


def test_every_family_has_a_mark_and_an_accent(site_out: Path) -> None:
    sheet = stylesheet(site_out)
    for family in FAMILIES:
        mark = family_mark(family)
        assert mark is not None
        assert (ROOT / "site" / mark).is_file()
        assert f".fam-{family}{{" in sheet


def test_an_unknown_family_falls_back_rather_than_breaking() -> None:
    assert family_mark("sinclair") is None


def test_a_page_declares_the_family_it_belongs_to(site_out: Path) -> None:
    assert 'class="fam-amiga"' in read(site_out, "amiga-500/index.html")
    assert 'class="fam-amiga"' in read(site_out, "amiga-500/mainboard-rev6a.html")
    assert 'class="fam-macintosh"' in read(site_out, "mac-se/index.html")


# --------------------------------------------------------------------------
# The cost of inlining the sheet into ninety pages
# --------------------------------------------------------------------------


def test_the_inlined_stylesheet_carries_no_comments(site_out: Path) -> None:
    sheet = stylesheet(site_out)
    assert "/*" not in sheet
    assert "\n\n" not in sheet


def test_compacting_keeps_what_css_cannot_lose() -> None:
    source = """
    /* a comment */
    .a  ,  .b { font-family: "IBM Plex Mono" , monospace ; }
    .c::before { content: "\\26A0\\FE0E  " }
    @font-face { src: url("../assets/fonts/x.woff2") format("woff2") }
    .d { border: 1px solid var(--rule) }
    """
    out = compact_css(source)
    assert "/*" not in out
    assert '"IBM Plex Mono",monospace' in out
    assert 'content:"\\26A0\\FE0E  "' in out
    assert 'url("../assets/fonts/x.woff2") format("woff2")' in out
    assert "border:1px solid var(--rule)" in out
    assert ".a,.b{" in out


def test_compacting_is_idempotent() -> None:
    source = (ROOT / "site" / "templates" / "style.css.j2").read_text(
        encoding="utf-8"
    )
    once = compact_css(source)
    assert compact_css(once) == once


def test_a_search_result_carries_the_family_it_belongs_to(site_out: Path) -> None:
    """The filter builds cards in the browser; they get the same accent."""
    index = read(site_out, "search-index.json")
    assert '"family": "amiga"' in index
    script = read(site_out, "search.js")
    assert 'entry.family ? "card fam-" + entry.family : "card"' in script
