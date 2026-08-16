# Safety

Read this before opening a power supply.

## Mains voltage

Power supply boards carry mains voltage. On a machine plugged into a Danish or
European outlet that is 230 V, enough to kill you. Unplug the machine and take
the cable out of the wall before opening anything.

## Capacitors hold a charge

Large filter capacitors stay charged after the machine is switched off and
unplugged, sometimes for a long time, and the charge on a 200 V snap-in is
dangerous on its own. Assume every capacitor in a PSU is live until you have
measured it.

Discharge deliberately, through a resistor rather than by shorting the terminals
with a screwdriver — shorting damages the board and throws sparks. Measure with
a meter afterwards and confirm the voltage is near zero before you touch
anything.

CRT machines — the Macintosh SE, SE/30 and Classic II in this dataset — add a
second hazard. The CRT anode holds a very high voltage and the tube itself can
implode if broken. If you have not worked on a CRT before, read up on
discharging one properly first, or have someone experienced do it.

## RIFA capacitors

The RIFA X2 film capacitors in these power supplies crack with age, absorb
moisture, and fail by exploding and filling the room with acrid smoke. They are
replaced unconditionally in this project, and they should be replaced before you
power a machine on, not after.

## Batteries

NiCd barrel batteries on Amiga 2000, 3000 and 500+ boards leak and destroy
traces. Remove them. Leaked electrolyte is corrosive — wear gloves, avoid
breathing the dust from a badly corroded board, and neutralise before cleaning.

## Soldering

Ventilate. Leaded and unleaded solder both produce fumes worth not inhaling, and
flux fumes are an irritant. Eye protection when clipping leads.

## On the data in this repository

The lists here are compiled from public sources and from boards contributors
have counted themselves. They are offered in good faith and they are not
guaranteed to be correct or complete for your particular board. Board revisions
vary, factories substituted parts, and previous owners modified machines.

**Verify against the board in front of you before ordering or installing
anything.** Pay particular attention to polarity, to voltage rating, and to
physical fit — height, diameter and lead spacing — where a part sits under a
shield or against a chassis.

Lists marked `derived` or `unverified` have not been confirmed against a cited
source. Treat them as a starting point for your own count, not as an answer.

Nobody involved in this project accepts liability for damage to your equipment
or injury to you. You are working on mains-powered equipment at your own risk.
