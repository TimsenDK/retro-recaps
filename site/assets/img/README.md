# Illustrations

Hand-written SVG. No editor metadata, no rasters, no external references —
every file is safe to inline or to reference with `<img>`.

Photographs under `machines/` are a separate set and are not described here.

## How to use them

**Inline them where you can.** Every drawing paints with `currentColor`, so an
inlined `<svg>` inherits the surrounding text colour and needs no theme work at
all: it follows light mode, dark mode, and the print stylesheet automatically.
Set the size on the element (`width`/`height` or `font-size` + `1em`); the files
carry a `viewBox` and no intrinsic size on purpose.

Referenced with `<img>` they still work: each file carries a three-line
stylesheet that only matches when the SVG is the root document (`svg:root`), so
it picks dark ink on a dark ground, light ink on a light one, and black when
printed. It cannot follow a site theme toggle that way, only the OS setting.

**Accessibility.** Every file opens with a `<title>`. Where the drawing repeats
a label that is already in the markup, hide it instead:
`<svg aria-hidden="true">` or `<img alt="">`. Never leave an `<img>` without an
`alt` attribute.

Nothing is distinguished by colour. The whole set reads correctly in one ink,
which is what the printed board sheet gets.

## Capacitor type symbols

One per value of the dataset's capacitor `type` enum, named
`cap-<type>.svg`. All ten share a grammar: the part is drawn in side view,
sitting on a line that represents the board, so lead placement and body shape —
the things a beginner actually confuses — are the difference between them.
A solid bar on the body is the polarity stripe and appears only on the polarised
types.

Intended size: 24–32 px in a table cell, up to ~200 px in a reference key.
All are **informative**.

| File | Reads as |
| --- | --- |
| `cap-electrolytic-radial.svg` | Upright can, both leads out of the bottom, stripe down one side. |
| `cap-electrolytic-axial.svg` | Can lying flat, one lead out of each end, bent down to the board. |
| `cap-electrolytic-snap-in.svg` | Large can on a moulded base with two short flat blade terminals. |
| `cap-electrolytic-smd.svg` | Can on a plastic seat with solder tabs — nothing passes through the board. |
| `cap-bipolar.svg` | Radial can with no stripe and a ± mark: no polarity to get wrong. |
| `cap-tantalum.svg` | Dipped bead with a **+** by one lead — tantalums mark the plus, not the minus. |
| `cap-film.svg` | Moulded box body, wide lead spacing, no polarity. |
| `cap-film-x2.svg` | Box film marked X2, with the two line conductors it bridges. |
| `cap-film-y2.svg` | Box film marked Y2, with the earth symbol it bridges to. |
| `cap-ceramic.svg` | Small disc on splayed leads. |

**`cap-film-x2.svg` and `cap-film-y2.svg` must never appear without their
class in text beside them.** The `X2`/`Y2` lettering inside the icon is legible
at 32 px and up, not at 24 px, and the two classes are not interchangeable on a
mains board. Same rule for `cap-tantalum.svg` if it is ever used to imply
polarity on its own: the reversed convention needs words.

## Polarity diagram

`polarity.svg` — three panels: the stripe and the long lead on the part, the
shaded half and the square pad on the board silkscreen, and what fitting one
backwards does. Carries its own labels.

The most useful drawing on the site and the one that earns space: intended at
**480–800 px wide**, in the reference section and on the printed sheet. Below
about 360 px the captions stop being readable — use it large or not at all.
**Informative.** Give it a real `alt`/`<desc>`; it already ships a `<desc>`.

The only colour in the set is the cross in the third panel
(`var(--warn-rule, #b13c22)`), and it is redundant — the panel is also captioned
and the shape is a cross.

## Family marks

`family-amiga.svg`, `family-commodore-8bit.svg`, `family-commodore-drive.svg`,
`family-macintosh.svg` — one per family in `FAMILY_NAMES`, keyed by the same id.

These are **machine silhouettes, not logos**: a wedge-profile computer, a
stepped breadbin-profile computer, a flat disk drive with a slot and two lamps,
an upright compact machine with a screen and a disk slot. No manufacturer mark
is reproduced or approximated, and none should be added later.

Intended size: 20–32 px beside a family heading or in a card. **Decorative** —
the family name is always in the markup, so mark them `aria-hidden`.

## Hazard mark

`hazard.svg` — triangle and bolt, the conventional high-voltage warning. Deliberately
plain: it labels the mains and CRT panels, and it is the one drawing on the site
that is not styled for period charm.

Intended size: 20–28 px, inline at the head of a `.hazard` panel, or up to 48 px
beside a full-width warning. It inherits `color`, so inside `.hazard` it picks up
`--warn-ink` on its own. **Informative**, and it never replaces the warning text
— it sits beside it.

## Other marks

`mark-counted.svg` — a tick inside a dashed component outline, for entries
verified against a physical board rather than a document. Intended size 16–24 px.
**Informative but never alone:** it means something specific and needs the word
(*verified*, *counted*) next to it.

`masthead-board.svg` — a board fragment with a DIP, two capacitor positions and
a few traces, drawn wide (`viewBox 0 0 160 32`) for a masthead rule or a page
header. Purely **decorative**; always `aria-hidden`.

## Not drawn

- **A separate CRT hazard mark.** The CRT panels warn about stored high voltage,
  which is what `hazard.svg` already says. A second, similar triangle would
  dilute the one mark the reader must not learn to skip.
- **A discharge-procedure icon.** Discharging safely is a sequence with a
  resistor and a meter in it. A 24 px picture of it would flatter the reader into
  thinking they had understood it; `SAFETY.md` explains it in words instead.
- **Verification-status icons for `derived` / `unverified`.** The site already
  distinguishes those with a coloured, worded badge. An icon would add a second
  vocabulary for the same thing.
