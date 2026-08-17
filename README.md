# Retro Recaps

An open dataset of electrolytic capacitor replacement lists for retro computers,
and a generated reference site built from it.

Recapping an old machine starts with the same question every time: which
capacitors, where, and rated for what? The answers are scattered across forum
threads, wikis, blog posts and dead links, and they disagree with each other.
This project collects them into one place, records where each list came from,
and is honest about which entries nobody has verified yet.

## Status

**Work in progress. Do not order parts from this dataset without checking the
sources yourself.**

The schema, the validator and the site generator are in place, and every board
file cites sources you can retrieve. But the dataset is young, it is still
changing week to week, and a recent audit of it found real errors — including a
mains-side rating that was wrong on a board marked as verified. Everything it
found has been acted on; the point is that a dataset this new will have more.

Treat a `verified` badge as "two independent sources agreed", not as "someone
held this board". Where the two differ, the board in your hands wins. Positions
marked `derived` or `unverified` say so for a reason, and open questions are
recorded rather than papered over.

Corrections from people with a board on the bench are the most useful thing
anyone can contribute here.

## Machines covered

| Family | Machines |
|---|---|
| Amiga | 500 (rev 3, 5, 6A/7, 8A) and its external supply, 1000 (NTSC and PAL), 2000 (rev 4 and 6.x), 3000 desktop — including PSUs |
| Commodore 8-bit | VIC-20, 16, Plus/4, 64 (five assemblies), 128, 128D, 128DCR |
| Commodore drives | 1541, 1541C, 1541-II, 1551, 1581 — including the drive motor-control boards |
| Macintosh | Classic II, SE, SE/30 — including all three supply makes |

19 machines, 86 board files. Several machines shipped on more than one PCB
assembly, and those assemblies differ at individual positions — match the
number printed on your board to the right file before ordering anything. Where
the dataset knows a board exists and does not cover it, the machine page says
so.

The Amiga 3000T is out of scope.

## How the data is organised

One file per board revision, under `data/<machine>/`. A machine's PSU, logic
board and analog board are separate files, because they are separate jobs and
because the same reference designators recur across them with different values.

Every board carries a verification status — `verified`, `derived` or
`unverified` — and its sources. A list nobody has confirmed says so, rather than
looking like the ones that have been.

Recommended parts live in `reference/`, keyed by manufacturer part number, so a
value used on a dozen boards is described once.

## Conventions

- 105 °C throughout, low-ESR in power supplies.
- Voltage ratings are revised upward where the original was lower, never
  downward. The original rating is kept in the data.
- RIFA-style mains film capacitors are replaced unconditionally, X- or
  Y-class. They fail explosively and a supply that lists none may simply never
  have been inventoried — boards record which of those two it is.
- NiCd batteries are removed; Mac PRAM batteries are replaced.
- On Macs, the logic board is recapped before the analog board.

## Safety

Power supply work involves mains voltage and capacitors that hold a charge after
the machine is unplugged. Read [SAFETY.md](SAFETY.md) before opening one.

## Contributing

Corrections are welcome, and the requirement is simple: a change to capacitor
data needs either a source URL or "I counted this on my own board" with a photo.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Working on the data locally

```bash
python -m pip install -e ".[dev]"
python -m tools validate --root .
python -m pytest
```

`validate` checks the dataset against the schema and against the project's
domain rules — that voltage is never revised downward, that a list marked
`verified` cites a source, that a pinned part actually fits the position. Errors
fail the build; warnings tell you what is still incomplete. The same command runs
on every pull request.

## Licence

Code is MIT. Data and documentation are CC BY-SA 4.0. See [LICENSE](LICENSE) and
[LICENSE-DATA](LICENSE-DATA).
