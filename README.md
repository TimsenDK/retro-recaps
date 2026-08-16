# Retro Recaps

An open dataset of electrolytic capacitor replacement lists for retro computers,
and a generated reference site built from it.

Recapping an old machine starts with the same question every time: which
capacitors, where, and rated for what? The answers are scattered across forum
threads, wikis, blog posts and dead links, and they disagree with each other.
This project collects them into one place, records where each list came from,
and is honest about which entries nobody has verified yet.

## Status

Early. The dataset is being migrated from a private spreadsheet; the site
generator is not built yet. See
[`docs/superpowers/specs/2026-08-16-retro-recaps-design.md`](docs/superpowers/specs/2026-08-16-retro-recaps-design.md)
for the design.

## Machines covered

| Family | Machines |
|---|---|
| Amiga | 500, 1000 (NTSC and PAL), 2000 (rev 4.x and 6.x), 3000 desktop — including PSUs |
| Commodore 8-bit | VIC-20 (both board types), 16, Plus/4, 64, 128, 128D |
| Commodore drives | 1541, 1541C, 1541-II, 1551, 1581 |
| Macintosh | Classic II, SE, SE/30 |

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
- RIFA X2 film capacitors are replaced unconditionally.
- NiCd batteries are removed; Mac PRAM batteries are replaced.
- On Macs, the logic board is recapped before the analog board.

## Safety

Power supply work involves mains voltage and capacitors that hold a charge after
the machine is unplugged. Read [SAFETY.md](SAFETY.md) before opening one.

## Contributing

Corrections are welcome, and the requirement is simple: a change to capacitor
data needs either a source URL or "I counted this on my own board" with a photo.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Code is MIT. Data and documentation are CC BY-SA 4.0. See [LICENSE](LICENSE) and
[LICENSE-DATA](LICENSE-DATA).
