"""A deliberately small Markdown renderer.

The site renders two Markdown files that live in this repository: `SAFETY.md`
and one section of `README.md`. Both are written by hand, in a narrow subset
of Markdown — headings, paragraphs, bullet lists, bold, inline code and
links. Rendering that subset is a hundred lines; taking a Markdown
dependency for it is not worth the supply chain.

Anything outside the subset is passed through as escaped text rather than
guessed at, so an unsupported construct shows up as literal characters on the
page instead of silently disappearing.
"""

from __future__ import annotations

import html
import re

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")


def render_inline(text: str) -> str:
    """Escape a run of text, then apply the inline subset."""
    escaped = html.escape(text, quote=False)
    escaped = _CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = _LINK_RE.sub(r'<a href="\2">\1</a>', escaped)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return escaped


def _blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Group lines into (kind, lines) blocks: heading, list or paragraph."""
    blocks: list[tuple[str, list[str]]] = []
    buffer: list[str] = []
    kind = "paragraph"

    def flush() -> None:
        nonlocal buffer, kind
        if buffer:
            blocks.append((kind, buffer))
        buffer = []
        kind = "paragraph"

    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            flush()
            continue
        if _HEADING_RE.match(stripped):
            flush()
            blocks.append(("heading", [stripped]))
            continue
        if _BULLET_RE.match(stripped):
            if kind != "list":
                flush()
                kind = "list"
            buffer.append(stripped)
            continue
        if kind == "list" and stripped.startswith("  "):
            # A wrapped continuation of the previous bullet.
            buffer[-1] = f"{buffer[-1]} {stripped.strip()}"
            continue
        if kind != "paragraph":
            flush()
        buffer.append(stripped)

    flush()
    return blocks


def render(text: str, heading_offset: int = 0) -> str:
    """Render the supported subset of `text` to an HTML fragment.

    `heading_offset` shifts every heading down a level, so a document whose
    own `# Title` is already shown as the page heading does not emit a second
    `<h1>`.
    """
    parts: list[str] = []
    for kind, lines in _blocks(text.splitlines()):
        if kind == "heading":
            match = _HEADING_RE.match(lines[0])
            assert match is not None
            level = min(len(match.group(1)) + heading_offset, 6)
            parts.append(f"<h{level}>{render_inline(match.group(2))}</h{level}>")
        elif kind == "list":
            items = "".join(
                f"<li>{render_inline(_BULLET_RE.match(line).group(1))}</li>"
                for line in lines
            )
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{render_inline(' '.join(lines))}</p>")
    return "\n".join(parts)


def section(text: str, title: str) -> str:
    """The body of the `## title` section, without its heading.

    Returns an empty string when no such heading exists, so a renamed
    section degrades to a missing block rather than a crash.
    """
    lines = text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line.rstrip())
        if match is None:
            continue
        if start is None:
            if match.group(2).strip().lower() == title.strip().lower():
                start = index + 1
                level = len(match.group(1))
            continue
        if len(match.group(1)) <= level:
            return "\n".join(lines[start:index])
    if start is None:
        return ""
    return "\n".join(lines[start:])
