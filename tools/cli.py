"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools",
        description=(
            "Validation and site generation for the Retro Recaps dataset."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="Check the dataset against the schema and the domain rules.",
    )
    validate.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=(
            "Repository root holding data/ and reference/ "
            "(default: current directory)."
        ),
    )
    validate.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors.",
    )

    build = subparsers.add_parser(
        "build-site",
        help="Render the dataset as a static site.",
    )
    build.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=(
            "Repository root holding data/, reference/ and site/ "
            "(default: current directory)."
        ),
    )
    build.add_argument(
        "--out",
        type=Path,
        default=Path("build"),
        help="Directory to write the site into (default: build).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        from tools.validate import run_validate

        return run_validate(root=args.root, strict=args.strict)

    if args.command == "build-site":
        from tools.site.build import run_build_site

        return run_build_site(root=args.root, out=args.out)

    parser.error(f"unhandled command: {args.command}")
    return 2
