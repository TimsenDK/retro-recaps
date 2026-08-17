"""Rendering the context to a directory of files.

This module is the only part of the site generator that touches the
filesystem or knows Jinja exists. It walks the context built by
:mod:`tools.site.context`, renders a page per view model, and writes the
board data files alongside their HTML.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from tools.loader import load_dataset
from tools.site import markdown
from tools.site.context import (
    VERIFICATION_ORDER,
    SiteContext,
    build_context,
    verification_view,
)

SITE_NAME = "Retro Recaps"
SITE_TAGLINE = (
    "Capacitor replacement lists for retro computers, with sources and an "
    "honest verification status."
)
REPO_URL = "https://github.com/TimsenDK/retro-recaps"
SITE_URL = "https://timsendk.github.io/retro-recaps"
CONTRIBUTE_URL = f"{REPO_URL}/blob/main/CONTRIBUTING.md"


def _environment(templates: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates)),
        autoescape=select_autoescape(["html", "html.j2"], default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def render_site(
    context: SiteContext,
    root: Path,
    out: Path,
    *,
    templates: Path | None = None,
    static: Path | None = None,
    assets: Path | None = None,
) -> list[Path]:
    """Write the whole site to `out`, returning every path written."""
    templates = templates or root / "site" / "templates"
    static = static or root / "site" / "static"
    assets = assets or root / "site" / "assets"
    env = _environment(templates)

    # The stylesheet is inlined into every page, so the URLs inside it are
    # resolved against the page, not against a stylesheet file. A page one
    # directory down needs `../assets/...` where the front page needs
    # `assets/...`, so the sheet is rendered once per depth the site has.
    stylesheets: dict[str, str] = {}

    def stylesheet_for(base: str) -> Markup:
        if base not in stylesheets:
            # `<style>` is raw text: a `"` escaped to `&#34;` is not decoded
            # back by the browser, it just makes `font-family: "IBM Plex
            # Mono"` unparseable. The sheet is ours, so it goes in as-is.
            stylesheets[base] = env.get_template("style.css.j2").render(base=base)
        return Markup(stylesheets[base])

    written: list[Path] = []

    def page(template_name: str, target: Path, base: str, **values: object) -> None:
        html = env.get_template(template_name).render(
            base=base,
            site=context,
            site_name=SITE_NAME,
            site_tagline=SITE_TAGLINE,
            site_url=SITE_URL,
            contribute_url=CONTRIBUTE_URL,
            stylesheet=stylesheet_for(base),
            **values,
        )
        _write(target, html)
        written.append(target)

    page("index.html.j2", out / "index.html", "")

    readme = _read_text(root / "README.md")
    conventions = markdown.section(readme, "Conventions")
    page(
        "reference.html.j2",
        out / "reference.html",
        "",
        conventions_html=Markup(
            markdown.render(conventions)
            if conventions
            else "<p>The conventions are not recorded in this build.</p>"
        ),
        verifications=[verification_view(s) for s in VERIFICATION_ORDER],
    )

    safety = _read_text(root / "SAFETY.md")
    page(
        "safety.html.j2",
        out / "safety.html",
        "",
        safety_html=Markup(
            markdown.render(safety)
            if safety
            else "<h1>Safety</h1><p>The safety text is missing.</p>"
        ),
    )

    page("status.html.j2", out / "status.html", "", status=context.status)

    for machine in context.machines:
        page(
            "machine.html.j2",
            out / machine.id / "index.html",
            "../",
            machine=machine,
        )
        for board in machine.boards:
            page(
                "board.html.j2",
                out / machine.id / f"{board.slug}.html",
                "../",
                board=board,
            )

    written.extend(_write_board_data(context, root, out))
    written.extend(_write_search(context, out))
    written.extend(_copy_tree(static, out))
    written.extend(_copy_tree(assets, out / "assets"))
    _prune_stale(out, written)
    return written


MANIFEST_NAME = ".build-manifest.json"
"""What the last build wrote, so this one can remove what it no longer writes.

Deleting a board file used to leave its page behind, and a stale page is worse
than a missing one: it is still reachable, still looks current, and still
lists parts. Pruning is driven by the previous manifest rather than by
whatever happens to sit in the output directory, so the generator only ever
removes files it put there itself.
"""


def _prune_stale(out: Path, written: list[Path]) -> None:
    manifest = out / MANIFEST_NAME
    current = sorted(path.relative_to(out).as_posix() for path in written)

    previous: list[str] = []
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, list):
            previous = [entry for entry in loaded if isinstance(entry, str)]

    root = out.resolve()
    for relative in set(previous) - set(current):
        stale = (out / relative).resolve()
        # A path that climbed out of `out` is not ours to touch, whatever the
        # manifest says.
        if root not in stale.parents or not stale.is_file():
            continue
        stale.unlink()

    # Empty directories left behind by the removals above. A symlinked
    # directory is left alone: following one would walk out of the output
    # tree, and removing it would take something that is not ours.
    for directory in sorted(
        (path for path in out.rglob("*") if path.is_dir() and not path.is_symlink()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if not any(directory.iterdir()):
            directory.rmdir()

    _write(manifest, json.dumps(current, indent=2) + "\n")


def _write_board_data(context: SiteContext, root: Path, out: Path) -> list[Path]:
    """The YAML behind each board, verbatim, and the same thing as JSON."""
    written: list[Path] = []
    dataset_dir = root / "data"
    for board in context.boards:
        source = dataset_dir / board.machine_id / f"{board.slug}.yaml"
        if not source.is_file():
            continue
        target_yaml = out / board.machine_id / f"{board.slug}.yaml"
        target_yaml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target_yaml)
        written.append(target_yaml)

        document = yaml.safe_load(source.read_text(encoding="utf-8"))
        target_json = out / board.machine_id / f"{board.slug}.json"
        _write(target_json, json.dumps(document, indent=2, ensure_ascii=False) + "\n")
        written.append(target_json)
    return written


def _write_search(context: SiteContext, out: Path) -> list[Path]:
    """The index as JSON for anyone consuming it, and as JS for the page.

    The page loads the `.js` form rather than fetching the `.json`, so search
    keeps working when the site is opened from a local directory where
    `fetch` of a sibling file is blocked.
    """
    payload = json.dumps(context.search, ensure_ascii=False)
    json_path = out / "search-index.json"
    js_path = out / "search-index.js"
    _write(json_path, payload + "\n")
    _write(js_path, f"window.RETRO_SEARCH = {payload};\n")
    return [json_path, js_path]


def _copy_tree(source_dir: Path, target_dir: Path) -> list[Path]:
    """Copy a directory verbatim, subdirectories and all.

    `site/static/` lands at the root of the site because its files are
    referenced by name (`search.js`); `site/assets/` lands under
    `assets/`, which is where the stylesheet and the templates look for
    fonts and images.
    """
    written: list[Path] = []
    if not source_dir.is_dir():
        return written
    for source in sorted(source_dir.rglob("*")):
        if not source.is_file():
            continue
        target = target_dir / source.relative_to(source_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)
    return written


def build_site(root: Path, out: Path) -> list[Path]:
    """Load the dataset and render it. Loader problems are not fatal here.

    `validate` is the command that judges the dataset; the site's job is to
    show what is there. A board that failed to load simply has no page.
    """
    dataset, _ = load_dataset(root)
    return render_site(build_context(dataset), root=root, out=out)


def run_build_site(root: Path, out: Path) -> int:
    written = build_site(root, out)
    pages = sum(1 for path in written if path.suffix == ".html")
    print(f"Wrote {pages} pages and {len(written)} files to {out}")
    return 0
