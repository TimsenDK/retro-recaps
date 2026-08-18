"""Rebuilding the self-hosted web fonts under `site/assets/fonts/`.

The `.woff2` files in that directory are checked in, because a site build
must not depend on the network. This module is how they were made, so that
anyone can reproduce them byte for byte instead of trusting a binary blob.

It is not part of the site build and is never run by it. Run it by hand
after `python -m pip install -e ".[fonts]"`:

    python -m tools.subset_fonts

Everything is drawn from the upstream `google/fonts` repository, which
carries the OFL licence text beside each family. The licences are copied
into `site/assets/fonts/` next to the fonts they cover.

The subset is deliberately small. The site is English, and the only
characters beyond ASCII it uses are the ones the data needs — `µ`, `°`,
`Ω` — plus typographic punctuation. Latin-1 and Latin Extended-A are kept
so that a name in a source citation survives.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl"
MIRROR = "https://api.github.com/repos/google/fonts/contents/ofl"

UNICODES = ",".join(
    (
        "U+0020-007E",  # ASCII
        "U+00A0-00FF",  # Latin-1: µ ° × · © ® and the accented letters
        "U+0100-017F",  # Latin Extended-A, for names in citations
        "U+0192,U+02C6,U+02DA,U+02DC",
        "U+2013-2014,U+2018-201A,U+201C-201E",
        "U+2020-2022,U+2026,U+2030,U+2039-203A,U+2044,U+2122",
        "U+03A9,U+03BC,U+2126",  # Ω, µ, and the ohm sign
        "U+2190-2193,U+2212,U+2264-2265",
    )
)

LAYOUT_FEATURES = "kern,liga,calt,ccmp,locl,mark,mkmk,tnum,zero,frac"

OHM_SIGN = 0x2126
GREEK_OMEGA = 0x03A9


def _download(family: str, name: str, target: Path) -> None:
    """Fetch one upstream file, falling back to the contents API.

    `raw.githubusercontent.com` rate-limits hard from some networks; the
    API serves the same bytes with an `Accept` header and is rarely
    throttled at the same time.
    """
    attempts = (
        (f"{UPSTREAM}/{family}/{name}", {}),
        (f"{MIRROR}/{family}/{name}", {"Accept": "application/vnd.github.raw"}),
    )
    errors: list[str] = []
    for url, headers in attempts:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
        except Exception as error:  # noqa: BLE001 - report every attempt
            errors.append(f"{url}: {error}")
            continue
        target.write_bytes(data)
        return
    raise SystemExit("could not fetch " + name + "\n  " + "\n  ".join(errors))


def _subset(source: Path, target: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "fontTools.subset",
            str(source),
            f"--unicodes={UNICODES}",
            f"--layout-features={LAYOUT_FEATURES}",
            "--flavor=woff2",
            "--with-zopfli",
            "--no-hinting",
            "--desubroutinize",
            "--drop-tables+=DSIG",
            "--name-IDs=0,1,2,3,4,5,6,13,14",
            f"--output-file={target}",
        ],
        check=True,
    )


def _map_omega_to_the_ohm_sign(font: Path) -> None:
    """Give U+03A9 the ohm glyph, for faces that only encode U+2126.

    IBM Plex Mono draws the ohm sign but not Greek capital omega, and the
    two are visually the same character. Which of the codepoints an ESR
    figure ends up carrying is not something the data can be relied on to
    settle, so the font answers to both rather than dropping to a fallback
    face mid-table.
    """
    from fontTools.ttLib import TTFont

    with TTFont(font) as opened:
        changed = False
        for table in opened["cmap"].tables:
            if OHM_SIGN in table.cmap and GREEK_OMEGA not in table.cmap:
                table.cmap[GREEK_OMEGA] = table.cmap[OHM_SIGN]
                changed = True
        if not changed:
            return
        opened.flavor = "woff2"
        opened.save(font)


def _instance(source: Path, target: Path, axes: list[str]) -> None:
    """Pin the axes the site does not use, keeping weight variable."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "fontTools.varLib.instancer",
            str(source),
            *axes,
            "-o",
            str(target),
        ],
        check=True,
    )


# (upstream family directory, upstream file, output name)
STATIC_FONTS = (
    # Bungee has one weight by design — the family varies by cut, not by
    # weight — so the masthead and the family headings take it at 400.
    ("bungee", "Bungee-Regular.ttf", "bungee-400.woff2"),
    ("chakrapetch", "ChakraPetch-Regular.ttf", "chakra-petch-400.woff2"),
    ("chakrapetch", "ChakraPetch-Bold.ttf", "chakra-petch-700.woff2"),
    ("ibmplexmono", "IBMPlexMono-Regular.ttf", "ibm-plex-mono-400.woff2"),
    ("ibmplexmono", "IBMPlexMono-Bold.ttf", "ibm-plex-mono-700.woff2"),
)

# The variable sans is instanced down to one axis: the site never asks for
# a condensed width, and dropping `wdth` is most of the file size.
VARIABLE_FONT = (
    "ibmplexsans",
    "IBMPlexSans[wdth,wght].ttf",
    "ibm-plex-sans-var.woff2",
    ["wdth=100", "wght=400:700"],
)

LICENCES = (
    ("bungee", "OFL.txt", "Bungee-OFL.txt"),
    ("chakrapetch", "OFL.txt", "ChakraPetch-OFL.txt"),
    ("ibmplexsans", "OFL.txt", "IBMPlex-OFL.txt"),
)

OHM_FIXUPS = ("ibm-plex-mono-400.woff2", "ibm-plex-mono-700.woff2")


def build_fonts(out: Path, cache: Path) -> list[Path]:
    cache.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for family, name, target_name in STATIC_FONTS:
        source = cache / f"{family}__{name}"
        if not source.is_file():
            _download(family, name, source)
        _subset(source, out / target_name)
        written.append(out / target_name)

    family, name, target_name, axes = VARIABLE_FONT
    source = cache / f"{family}__{name}"
    if not source.is_file():
        _download(family, name, source)
    instanced = cache / f"{family}__instanced.ttf"
    _instance(source, instanced, axes)
    _subset(instanced, out / target_name)
    written.append(out / target_name)

    for name in OHM_FIXUPS:
        _map_omega_to_the_ohm_sign(out / name)

    for family, name, target_name in LICENCES:
        source = cache / f"{family}__{name}"
        if not source.is_file():
            _download(family, name, source)
        shutil.copyfile(source, out / target_name)
        written.append(out / target_name)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "site" / "assets" / "fonts",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".font-cache",
        help="Where the upstream originals are kept between runs.",
    )
    args = parser.parse_args(argv)
    written = build_fonts(args.out, args.cache)
    total = sum(path.stat().st_size for path in written if path.suffix == ".woff2")
    print(f"Wrote {len(written)} files to {args.out} ({total} bytes of font)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
