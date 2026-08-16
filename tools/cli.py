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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        from tools.validate import run_validate

        return run_validate(root=args.root, strict=args.strict)

    parser.error(f"unhandled command: {args.command}")
    return 2
