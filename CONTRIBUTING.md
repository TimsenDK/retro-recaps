# Contributing

Corrections and additions are welcome. The dataset is only worth anything if it
is right, so most of this document is about evidence.

## The rule

**A change to capacitor data needs evidence.** One of:

- a source URL — a service manual, a wiki page, a forum thread, a blog post; or
- "I counted this on my own board", with a photo of the board.

Without evidence the dataset becomes folklore, and folklore is what this project
exists to replace. A pull request that changes values without a source will be
asked for one before it is merged.

If your source disagrees with what is already recorded, say so in the pull
request and cite both. Conflicting sources are useful information, and the board
file can record the disagreement in a note.

## What to work on

The [status page](https://github.com/TimsenDK/retro-recaps) lists what is
missing: boards marked `unverified`, positions without reference designators,
and machines still to be migrated.

Two entries there are worth calling out, because no public list appears to exist
for either and someone has to count them on a physical board: the **Commodore
1551** and the **Commodore 1581 logic board**.

## Making a change

1. Fork, and make a branch.
2. Edit the YAML under `data/` or `reference/`.
3. Run `python -m tools validate` and fix anything it reports.
4. Open a pull request describing what changed and citing your evidence.

Validation also runs in CI, and a pull request that fails it will not be merged.
Warnings do not block anything; errors do.

## Data conventions

Follow what is already there, and in particular:

- One file per board revision. A machine's PSU, logic board and analog board are
  separate files. The same reference designators recur across boards of one
  machine with different values, so never merge them.
- Voltage is revised upward where the original was lower, never downward. Keep
  the original in `original_voltage_v`.
- 105 °C parts throughout; low-ESR in power supplies.
- Set `verification` honestly. `verified` requires a source and validation
  enforces that. If you inferred an entry, mark it `derived` and explain how in
  a note.
- Do not add prices or stock levels. They go stale in days. Part numbers are
  fine; the site links out for the rest.

### `revisions:` — what is printed on the board

A board's `revisions:` list identifies the PCB, and identifies it the way the
board itself does. Where an assembly number is silkscreened on the board, that
number is the revision:

```yaml
revisions:
  - 250407
```

Not the schematic number, and not an `ASSY` prefix. Where no assembly number
exists, the revision letter or number the board carries stays as it is — `6A`,
`4.x`, `all known`.

**The bare number is right where one assembly maps to exactly one file.** Where
one assembly number legitimately spans two files — the same PCB stuffed two
ways, or two revisions of one assembly that take different lists — the number
alone no longer identifies anything, and the revision carries the number plus
what distinguishes it:

```yaml
revisions:
  - 310379 rev 6      # in one file
  - 310379 rev 7      # in the other
```

Two files of one machine and one board kind may not claim the same revision
string. The validator errors on it, because the reader could not tell which
list applies to the board in front of them — which is the same reason the
qualifier belongs in the revision rather than only in a note.

Everything beyond the identifier is prose, and prose goes in `notes:`. A
revision string like `250407 (120 VAC/60 Hz variant)` becomes the revision
`250407` plus a note saying the board is the 120 VAC/60 Hz variant — unless the
120 VAC board is a second file sharing that assembly number, in which case the
mains variant is what distinguishes it and belongs in the revision.

### `mains:` — what the PCB actually carries

```yaml
mains: true    # or false
```

**Required on every `board: psu` and every `board: analog`.** This is what
drives the mains hazard panel on the site — the board kind does not, because
the kind gets it wrong in both directions. A 1541 longboard mainboard carries
the machine's linear supply and is `mains: true`. A 1541-II analog board is
low-voltage motor control and is `mains: false`. Declare it on any other board
kind that carries mains, too.

Undeclared, only a `psu` is treated as mains-carrying. So an analog board with
no declaration gets a hedging "check what this board carries" warning rather
than a confident one, which is worse for the reader than either answer. State
it.

Where you cannot establish it and the board might carry mains, the conservative
answer wins: `mains: true`.

### `x2_filter:` — the mains input filter

```yaml
x2_filter: listed    # or absent | unknown
```

Expected on every mains-carrying board, and rejected on one that is not.

- `listed` — a mains film position appears in `capacitors:` below, either
  `film-x2` or `film-y2`. The validator errors if neither does.
- `absent` — a source positively establishes the board has no mains film
  capacitor.
- `unknown` — nobody has inventoried it.

**Source silence is `unknown`, never `absent`.** RIFA-style mains film
capacitors fail explosively and are replaced unconditionally; a board wrongly
marked `absent` tells a reader there is nothing to look for.

Record the class the part actually is. `film-x2` sits across live and neutral;
`film-y2` bridges the isolation barrier, and the two carry different voltage
floors, so recording a Y-class part as `film-x2` describes the wrong component
however close the value is.

### `designators_unknown:` and `original_voltage_unknown:`

```yaml
- designators_unknown: true          # instead of `designators:`
  original_voltage_unknown: true     # instead of `original_voltage_v:`
```

Each marker is mutually exclusive with the field it stands in for, and each
must be `true` — the schema rejects both the pair and a `false`.

These say **the public record does not contain this**, which is different from
nobody having filled the field in, and they turn off the warning that would
otherwise ask for it. That makes them easy to misuse: do not reach for one to
silence a warning where the answer is retrievable. If the source you cited
states the factory rating, record the rating. `original_voltage_v` is recorded
whenever it is known, even when it equals `voltage_v`.

### `series:`, `part:` and the voltage range

Every position needs a `series:` or a `part:`; the validator errors on one that
has neither, because the site then has nothing to recommend and a position
nobody can buy a part for is usually a position that does not exist.

A series in `reference/series.yaml` may record the working voltages it is made
in:

```yaml
- id: panasonic-fr
  voltage_min_v: 6.3
  voltage_max_v: 100
```

Where a range is recorded, a position rated outside it is an error: the series
is the right type and the file validates, but the reader is sent to a catalogue
page that does not stock the rating. Add the range from the manufacturer's
datasheet when you add a series, and reach for a different series rather than
widening a range to fit a position.

### Sources

A board that lists any capacitor position needs at least one source; that is an
error, not a warning. A positionless `unverified` stub may cite nothing — it
asserts nothing, so it owes nothing.

A `verified` badge wants two independently retrieved sources covering that
exact assembly. One source and a `verified` badge is a warning: nothing
corroborates it if that source turns out to be wrong or unreadable. A position
may be marked less certain than its board, never more.

### Referring to another file from a note

A note may point at another board or machine. Write the reference as the path
relative to `data/`, and nothing else:

```yaml
notes:
  - The same list applies to commodore-128/mainboard-rev6.yaml.
  - Shipped with the drive described in commodore-1541/machine.yaml.
```

The generator turns each of those into a link to the published page, replacing
the filename with the page's own name. Two forms that look reasonable do not
work and are left as dead text on the page:

- a bare filename — `psu.yaml` — because nothing says which machine's supply;
- a relative path — `../commodore-128/mainboard-rev6.yaml` — because it encodes
  where the writer was standing rather than what is being referred to.

`<machine-id>/<file>.yaml` is resolvable from anywhere, which is the whole
point. A reference that names no file in the dataset stays as plain text rather
than becoming a broken link, so a typo is silent — check the built page.

### Board maps

A layout file lives at `data/<machine>/layout-<board-file-stem>.yaml` — the
same machine directory as the board it maps, named after the board file it
maps. It never carries a capacitance, a voltage, a quantity or a part number;
those stay in the board file, because a second place for a value is a second
place for it to be wrong.

`python -m tools validate` checks a layout's capacitor designators against
its board's list, and the match must be exact: a position the board does not
list is an error, and a position the board lists that the map leaves out is
an error too — the second is the more dangerous one, since it reads as "there
is no capacitor there" to someone holding the board.

Set `precision` honestly. `measured` means the positions were read off a
board layout drawing; `approximate` means they were read off a photograph.
Declaring `approximate` is required, not optional — the map renders it as a
dashed ring and says so on the page, and a photograph-derived position
claiming `measured` misleads exactly the reader it's supposed to help. A
layout also carries its own `verification` and `sources`, independent of the
board's.

A correction to a position is as welcome as a correction to a value, and
needs the same evidence.

## Style

Written content in this repository is in English, including YAML notes and
commit messages.

Commit messages follow Conventional Commits — `data:`, `feat:`, `fix:`,
`docs:`, `chore:` — with the machine in the subject where it applies, for
example `data: correct C401 value on A500 rev 6A`.

## Code

`tools/` is a Python package. Tests are pytest, run with `pytest`. New domain
rules in the validator want a test with a fixture that fails without them.

## Safety

If you are contributing power supply data, please read [SAFETY.md](SAFETY.md)
first, and do not encourage anyone in an issue or a note to skip discharging a
supply.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
