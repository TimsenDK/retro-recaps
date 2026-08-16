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
