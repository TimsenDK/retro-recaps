"""What the search box does with a value nobody can type.

`search.js` is the one piece of behaviour on the site that is not rendered by
the generator, and the µ in every capacitance is on no keyboard anyone owns.
These tests run the real file under Node against the real index, so the
folding rules cannot rot silently. They skip where Node is absent rather than
making it a build dependency.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEARCH_JS = ROOT / "site" / "static" / "search.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node is not installed"
)

# One board with a 3300 µF position, written the way the generator writes it.
INDEX = [
    {
        "type": "board",
        "title": "Amiga 500 — Mainboard — 5",
        "subtitle": "Verified",
        "family": "amiga",
        "url": "amiga-500/mainboard-rev5.html",
        "status": "verified",
        "text": "amiga 500 a500 mainboard 5 c401 c402 3300 µf 25 v",
    },
    {
        "type": "machine",
        "title": "Macintosh SE",
        "subtitle": "Macintosh",
        "family": "macintosh",
        "url": "mac-se/index.html",
        "status": "derived",
        "text": "macintosh se mac se",
    },
]

HARNESS = """
const fs = require("fs");
// With `node -e`, argv[0] is the executable and the arguments after
// `--` start at argv[1].
const idx = JSON.parse(process.argv[1]);
const queries = JSON.parse(process.argv[2]);

function el(id) {
    return {
        id, style: {}, hidden: false, textContent: "", value: "",
        selectionStart: 0, selectionEnd: 0, children: [],
        appendChild(c) { this.children.push(c); },
        addEventListener(name, fn) { (this.handlers ||= {})[name] = fn; },
        setSelectionRange(a) { this.selectionStart = this.selectionEnd = a; },
        focus() {},
    };
}
const nodes = {
    "search-box": el("search-box"), "search-keys": el("search-keys"),
    "search": el("search"), "search-results": el("search-results"),
    "everything": el("everything"),
};
global.window = { RETRO_SEARCH: idx };
global.document = {
    documentElement: { classList: { add() {} } },
    getElementById: (id) => nodes[id] || null,
    createElement: () => ({ appendChild() {}, style: {} }),
};
eval(fs.readFileSync(process.argv[3], "utf8"));

const input = nodes.search, results = nodes["search-results"];
const out = {};
for (const q of queries) {
    input.value = q;
    results.children = [];
    input.handlers.input();
    out[q] = { hits: results.children.length, hidden: results.hidden };
}
// A button press inserts at the caret and re-runs the filter.
input.value = "3300 25";
input.selectionStart = input.selectionEnd = 4;
results.children = [];
nodes["search-keys"].handlers.click({
    target: { closest: () => ({ getAttribute: () => "µF" }) },
});
out["__button__"] = { value: input.value, hits: results.children.length };
console.log(JSON.stringify(out));
"""


def run(queries: list[str]) -> dict:
    result = subprocess.run(
        [
            "node",
            "-e",
            HARNESS,
            "--",
            json.dumps(INDEX),
            json.dumps(queries),
            str(SEARCH_JS),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def test_every_way_of_writing_a_value_finds_the_same_board() -> None:
    """'3300µF', '3300uf' and the Greek mu all mean the 3300 µF position.

    The index holds '3300 µf'. A reader types it without the space, or types
    'uf' because µ is on no keyboard, or pastes U+03BC from a datasheet. A
    search that is right in every way that matters must not answer 'nothing
    matches'.
    """
    written = ["3300 µF", "3300µF", "3300uf", "3300μF", "3300 UF"]
    hits = run(written)
    assert [hits[q]["hits"] for q in written] == [1] * len(written)


def test_a_designator_still_finds_its_board() -> None:
    assert run(["c401"])["c401"]["hits"] == 1


def test_a_query_matching_nothing_says_so_rather_than_listing_everything()\
        -> None:
    """The one card rendered is the 'nothing matches' message."""
    result = run(["zzzz"])["zzzz"]
    assert result["hits"] == 1
    assert result["hidden"] is False


def test_a_key_inserts_at_the_caret_and_refilters() -> None:
    """Someone correcting the middle of a query gets the µF where they are."""
    result = run(["3300"])["__button__"]
    assert result["value"] == "3300µF 25"
    assert result["hits"] == 1
