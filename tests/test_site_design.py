"""The visual layer: machine pictures, family accents, symbols, polarity.

The picture tests are the load-bearing ones, and they pull in two directions at
once. CC BY and CC BY-SA oblige the site to name every photographer, so the
credits page must list all of them — but the credit is deliberately kept off
the pictures themselves, so no machine page and no card may carry one. Both
halves are asserted here. The rest is shape: every picture is processed to one
size, because a row of cards of different heights was the reason for processing
them at all. The contrast tests are the other kind of obligation: the family
accents are computed against the backgrounds they actually sit on rather than
judged by eye.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from markupsafe import Markup, escape

from tools.loader import load_dataset
from tools.model import Board, Capacitor, Dataset, Layout, LayoutFeature
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
from tools.site.layout import LayoutView, layout_view

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
# The machine pictures, and where their credit lives
# --------------------------------------------------------------------------

FULL_SIZE = (1280, 800)
CARD_SIZE = (640, 400)


def test_the_recorded_pictures_are_all_readable_and_measurable() -> None:
    photos = load_photos(ASSETS)
    assert photos, "images.yaml records no pictures"
    for photo in photos.values():
        assert (ASSETS / "img" / "machines").joinpath(
            Path(photo.url).name
        ).is_file(), photo.machine_id
        assert photo.width and photo.height, photo.machine_id
        assert photo.card_width and photo.card_height, photo.machine_id


def test_every_picture_is_processed_to_the_same_shape() -> None:
    """One shape for the set: the cards are one height, or they are not."""
    for photo in load_photos(ASSETS).values():
        assert (photo.width, photo.height) == FULL_SIZE, photo.machine_id
        assert (photo.card_width, photo.card_height) == CARD_SIZE, photo.machine_id


def test_every_picture_names_its_photographer_and_licence() -> None:
    for photo in load_photos(ASSETS).values():
        assert photo.author, photo.machine_id
        assert photo.licence, photo.machine_id
        if photo.requires_attribution:
            assert photo.licence_url, photo.machine_id
            # A generated picture is the project's own and has no source page
            # to point at; everything photographed by someone else has one.
            if not photo.generated:
                assert photo.source_url, photo.machine_id


def test_an_entry_that_cannot_be_credited_is_not_published(tmp_path: Path) -> None:
    """A picture without a photographer is one we may not lawfully show."""
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


def test_the_credits_page_lists_every_picture_the_site_shows(
    site_out: Path,
) -> None:
    """The obligation is met on one page, so that page has to be complete."""
    page = read(site_out, "image_credits.html")
    for photo in load_photos(ASSETS).values():
        # One photographer is credited with a quoted pseudonym, so the name
        # reaches the page escaped, exactly as the template escapes it.
        assert escape(photo.author) in page, photo.machine_id
        assert photo.licence in page, photo.machine_id
        if photo.requires_attribution:
            assert photo.licence_url in page, photo.machine_id
            assert photo.source_url in page, photo.machine_id


def test_the_credits_page_says_the_pictures_were_altered(site_out: Path) -> None:
    """Declaring the modification is a licence condition, not a courtesy."""
    page = read(site_out, "image_credits.html")
    assert "cropped" in page
    assert "cel-shad" in page


def test_every_page_links_to_the_credits(site_out: Path) -> None:
    for relative in ("index.html", "amiga-500/index.html", "reference.html"):
        assert "image_credits.html" in read(site_out, relative), relative


def test_no_credit_is_rendered_beside_a_picture(site_out: Path) -> None:
    """The credit lives on one page; the pages with pictures stay clear."""
    photographers = {photo.author for photo in load_photos(ASSETS).values()}
    for relative in ("index.html", "amiga-500/index.html"):
        page = read(site_out, relative)
        assert 'class="credit"' not in page, relative
        assert "commons.wikimedia.org" not in page, relative
        for author in photographers:
            assert str(escape(author)) not in page, f"{relative}: {author}"


def test_the_generated_pictures_say_so_where_it_can_be_read(
    site_out: Path,
) -> None:
    """Nothing is printed under a picture, so the alt text has to carry it.

    A generated machine must not be able to pass as a photographed one for a
    reader who cannot see it, and the credits page has to say which is which.
    """
    photos = load_photos(ASSETS)
    generated = {i for i, photo in photos.items() if photo.generated}
    # The set is mostly drawn now: only these four are still photographs.
    photographed = {i for i, photo in photos.items() if not photo.generated}
    assert photographed == {
        "commodore-128",
        "mac-classic-ii",
        "mac-se",
        "mac-se30",
    }

    for machine_id in generated:
        assert "generated illustration" in photos[machine_id].alt, machine_id

    credits = read(site_out, "image_credits.html")
    assert "generated illustration" in credits
    assert "not photographs at all" in credits


def test_nothing_is_printed_under_a_picture(site_out: Path) -> None:
    """The design carries no line under the frame — not a credit, not a label."""
    rendered = render_machine_page(load_photos(ASSETS)["commodore-128dcr"])
    assert "<figcaption" not in rendered
    for relative in ("index.html", "amiga-500/index.html"):
        assert "<figcaption" not in read(site_out, relative), relative


def test_a_photographed_picture_is_not_labelled_as_generated() -> None:
    photo = load_photos(ASSETS)["commodore-128"]
    assert not photo.generated
    assert "photographed" in photo.alt


def test_an_index_card_picture_opens_the_machine(site_out: Path) -> None:
    """The picture in a card reads as clickable, so it is."""
    page = read(site_out, "index.html")
    card = re.search(r'<li class="card[^>]*>.*?</li>', page, re.S)
    assert card is not None
    markup = card.group(0)
    link = re.search(r'<a class="shotlink" href="([^"]+)">\s*<img[^>]*>', markup, re.S)
    assert link is not None
    target = link.group(1)
    assert target.endswith("/index.html")
    # The same target as the card's own text link, not a second destination.
    assert markup.count(f'href="{target}"') == 2


def test_the_picture_on_a_machine_page_is_not_a_link(site_out: Path) -> None:
    """It is already that page: a link to itself is a trap, not a shortcut."""
    page = read(site_out, "amiga-500/index.html")
    shot = re.search(r'<figure class="shot">.*?</figure>', page, re.S)
    assert shot is not None
    assert "<a" not in shot.group(0)


def test_a_card_opens_its_page_from_anywhere_in_the_box(site_out: Path) -> None:
    """Clicking a card anywhere opens it, without nesting one link in another.

    The mechanism is the card's own link stretched over the box, so what the
    markup must guarantee is that there is exactly one such link per card and
    that the stylesheet stretches it.
    """
    sheet = stylesheet(site_out)
    assert ".card>a::after" in sheet
    assert ".card:focus-within" in sheet

    machine_page = read(site_out, "amiga-500/index.html")
    boards = re.search(r'<ol class="cards">.*?</ol>', machine_page, re.S)
    assert boards is not None
    for card in re.findall(r"<li class=\"card\">.*?</li>", boards.group(0), re.S):
        own_links = re.findall(r"^\s*<a href=\"([^\"]+)\"", card, re.M)
        assert len(own_links) == 1, card
        assert own_links[0].endswith(".html")


def test_a_picture_reserves_its_box_before_it_loads(site_out: Path) -> None:
    photo = load_photos(ASSETS)["amiga-500"]
    page = read(site_out, "amiga-500/index.html")
    tag = re.search(r"<img[^>]*" + re.escape(photo.url) + r"[^>]*>", page)
    assert tag is not None
    markup = tag.group(0)
    assert f'width="{photo.width}"' in markup
    assert f'height="{photo.height}"' in markup
    assert 'loading="lazy"' in markup


def test_a_picture_has_alt_text_that_describes_the_machine(
    site_out: Path,
) -> None:
    page = read(site_out, "amiga-500/index.html")
    tag = re.search(r"<img[^>]*machines/amiga-500\.jpg[^>]*>", page)
    assert tag is not None
    alt = re.search(r'alt="([^"]*)"', tag.group(0))
    assert alt is not None
    assert "Amiga 500" in alt.group(1)


def test_a_machine_with_no_picture_still_renders_its_frame(
    site_out: Path,
) -> None:
    """One machine in the set has no acceptably licensed photograph."""
    page = read(site_out, "mac-se/index.html")
    assert "machines/mac-se.jpg" in page

    pictureless = render_pictureless()
    assert "No freely licensed photograph" in pictureless
    assert 'class="shot"' in pictureless
    assert "machines/" not in pictureless


def render_machine_page(photo: object | None) -> str:
    """One machine page rendered with whatever picture is handed to it."""
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
        photo=photo,
    )


def render_pictureless() -> str:
    """The Amiga 500 page as it would render with no picture recorded.

    The fixture dataset holds machines the real site has pictures of, so the
    empty case is exercised by building one page without them rather than by
    depending on which machine happens to be missing one.
    """
    return render_machine_page(None)


def test_jpeg_size_reads_the_real_files() -> None:
    path = ASSETS / "img" / "machines" / "amiga-500-card.jpg"
    assert jpeg_size(path) == CARD_SIZE


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
# The board map
# --------------------------------------------------------------------------


def test_a_board_with_a_map_renders_it_inline(site_out: Path) -> None:
    page = read(site_out, "amiga-500/mainboard-rev6a.html")
    assert '<figure class="boardmap">' in page
    assert "<svg" in page
    assert 'id="pos-' in page


def test_a_board_with_no_map_renders_none_of_its_furniture(site_out: Path) -> None:
    page = read(site_out, "amiga-500/psu.html")
    assert "boardmap" not in page


def test_every_row_in_the_table_is_addressable(site_out: Path) -> None:
    page = read(site_out, "amiga-500/mainboard-rev6a.html")
    assert 'data-designator="C321"' in page


def test_the_board_map_is_the_one_picture_that_prints(site_out: Path) -> None:
    """The map stays on the printed sheet.

    Styled by shape, not by the `.boardmap` class: the stylesheet is inlined
    into every page, and a class rule naming "boardmap" would put that word
    into the print block of a page with no map, tripping
    test_a_board_with_no_map_renders_none_of_its_furniture. `figure` reaches
    it the same way the screen rules do (see the "board map" section above).
    """
    sheet = stylesheet(site_out)
    print_block = sheet.split("@media print", 1)[1]
    hidden = " ".join(
        re.findall(r"([^{}]*)\{[^{}]*display:\s*none[^{}]*\}", print_block)
    )
    assert ".shot" in hidden
    assert "figure" not in hidden
    compact = print_block.replace(" ", "").replace("\n", "")
    assert "figure{break-inside:avoid" in compact
    assert ".poscircle{fill:#fff}" in compact
    assert "boardmap" not in print_block


def test_the_board_page_ships_the_highlight_script_and_degrades_without_it(
    site_out: Path,
) -> None:
    page = read(site_out, "amiga-500/mainboard-rev6a.html")
    assert "boardmap.js" in page
    assert (site_out / "boardmap.js").is_file()
    # With no JS at all the designator is still printed beside the ring.
    assert ">C321<" in page


def demo_layout(designators: list[str], *, precision: str = "measured") -> Layout:
    """A minimal, otherwise-unremarkable layout placing the given designators."""
    return Layout(
        id="demo-layout",
        board="amiga-500-mainboard-rev6a",
        precision=precision,
        verification="derived",
        orientation="Drawn for a test, not for a bench.",
        width=100,
        height=100,
        features=tuple(
            LayoutFeature(kind="capacitor", x=0.5, y=0.5, designator=designator)
            for designator in designators
        ),
    )


def render_board_page_with(layout: LayoutView) -> str:
    """The Amiga 500 rev 6A board page rendered with a stand-in layout.

    Reuses the fixture board's own view rather than hand-building one: a
    `BoardView` carries dozens of fields the template touches, and the point
    of this test is the caption wording, not re-deriving every one of them.
    """
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

    dataset, _ = load_dataset(FIXTURES / "site")
    context = build_context(dataset)
    board = next(b for b in context.boards if b.id == "amiga-500-mainboard-rev6a")
    board = dataclasses.replace(board, layout=layout)
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "site" / "templates")),
        autoescape=select_autoescape(["html", "html.j2"], default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("board.html.j2").render(
        base="../",
        site=context,
        site_name="Retro Recaps",
        site_tagline="",
        site_url="",
        contribute_url="",
        stylesheet="",
        board=board,
        polarity_svg=Markup(""),
    )


def test_an_approximate_map_says_so_in_words() -> None:
    """A dash pattern is not a disclosure — someone has to be able to read it."""
    view = layout_view(demo_layout(["C1"], precision="approximate"))
    assert view.is_approximate
    rendered = render_board_page_with(view)
    assert "approximate" in rendered
    assert "read from a photograph" in rendered


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
