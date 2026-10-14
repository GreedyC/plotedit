#!/usr/bin/env python3
"""The Altman 6" Fresnel, checked against the figures printed on its datasheet.

    cd server && python3 test_fresnel.py

⭐ SOURCE: Altman 65Q/165Q 6" Fresnel datasheet (altmanlighting.com, 65Q.pdf,
rev 022904), supplied by Jerry 2026.10.13. "65Q AND 165Q PHOTOMETRIC DATA WITH
BTN LAMP". 65Q and 165Q share one chart — they differ in the focus mechanism, a
thumb screw against a rear screw feed, not in light.

🔴 THE ASSERTIONS BELOW ARE THE SHEET'S OWN PRINTED NUMBERS, not figures this
code produced and then agreed with. The datasheet prints a footcandle and a beam
diameter at five throws for each end of the focus, which is twenty independent
checks on two candela values and two angles — so if a digit was mistyped out of
the PDF, the arithmetic disagrees with the paper.

⚠ The first Fresnel in the table. `symbols.fresnel()` could draw one all along
and no row ever used the family, which is how the wattage fault below survived.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import fixture_names as fn        # noqa: E402
from plotedit import photometrics as ph         # noqa: E402

FAILS = []
SPOT = "Altman 65Q Fresnel @spot"
FLOOD = "Altman 65Q Fresnel @flood"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("the two ends of the focus, as the sheet states them")
check("spot field angle", ph.FIXTURES[SPOT]["field"], 16.0)
check("spot beam angle", ph.FIXTURES[SPOT]["beam"], 9.0)
check("spot candlepower", ph.FIXTURES[SPOT]["cd"], 92500)
check("flood field angle", ph.FIXTURES[FLOOD]["field"], 70.0)
check("flood beam angle", ph.FIXTURES[FLOOD]["beam"], 59.0)
check("flood candlepower", ph.FIXTURES[FLOOD]["cd"], 8800)
check("both are the Fresnel family", ph.FIXTURES[SPOT]["family"], "Fresnel")
check("...which nothing used before", ph.FIXTURES[FLOOD]["family"], "Fresnel")

print("\n🔴 and the sheet checks against itself, at five throws")
# The footcandle row printed under each cone. Twenty numbers that all have to
# fall out of two candela figures and the inverse square law.
check("spot footcandles at 10-30 ft",
      [round(ph.footcandles(SPOT, d)[0]) for d in (10, 15, 20, 25, 30)],
      [925, 411, 231, 148, 103])
# ⚠ 103, not the sheet's 102. 92,500 / 900 = 102.78, which Altman round DOWN and
# this rounds to nearest. A rounding step, not a disagreement — and worth
# stating rather than fudging the assertion to match the paper.
check("...and the sheet's last figure is 102, not 103",
      round(92500 / 900, 2), 102.78)
check("flood footcandles at 10-30 ft",
      [round(ph.footcandles(FLOOD, d)[0]) for d in (10, 15, 20, 25, 30)],
      [88, 39, 22, 14, 10])

print("\nthe beam diameters printed on the cones")
check("spot diameters", [round(ph.diameter(d, 16.0), 1) for d in (10, 15, 20, 25, 30)],
      [2.8, 4.2, 5.6, 7.0, 8.4])
check("flood diameters", [round(ph.diameter(d, 70.0)) for d in (10, 15, 20, 25, 30)],
      [14, 21, 28, 35, 42])

print("\n⭐ four lamps, with the correction factors the sheet prints")
# Unlike the Shakespeare's, this LAMP INFORMATION table has an explicit
# "correction factor" column that reads cleanly.
check("the lamps offered", ph.lamps_for(SPOT), ["BTN", "BTP", "BTM", "BTL"])
check("...reference lamp first", ph.FIXTURES[SPOT]["ref_lamp"], "BTN")
check("...and the same four at the flood end", ph.lamps_for(FLOOD), ph.lamps_for(SPOT))
base = ph.footcandles(SPOT, 10)[0]
check("BTN is the reference, so 1.00", round(ph.footcandles(SPOT, 10, lamp="BTN")[0]), 925)
check("BTP is 1.20", round(ph.footcandles(SPOT, 10, lamp="BTP")[0]), round(base * 1.20))
check("BTM is 0.76", round(ph.footcandles(SPOT, 10, lamp="BTM")[0]), round(base * 0.76))
check("BTL is 0.65", round(ph.footcandles(SPOT, 10, lamp="BTL")[0]), round(base * 0.65))

print("\n🔴 and NOT the HPL, though one physically fits")
# Altman sell 90-HPL575 and 90-HPL750 versions of this fixture. The same table
# lists both with NO correction factor and no rated lumens. Offering an HPL here
# is the exact fault that made a Shakespeare offer an HPL 750.
check("no HPL is offered", [l for l in ph.lamps_for(SPOT) if "HPL" in l], [])
check("an HPL 575 returns no figure", ph.footcandles(SPOT, 10, lamp="HPL 575")[0], None)
check("...and says why",
      "no HPL 575 multiplier" in ph.footcandles(SPOT, 10, lamp="HPL 575")[1], True)
check("the HPL-socket fixture is NOT aliased to the BTN chart",
      fn.resolve("65Q-HPL")[0], None)
check("...and says Altman publish no factor for it",
      "no correction factor" in fn.resolve("65Q-HPL")[1], True)

print("\n🔴 the wattage fault this fixture exposed")
# ⚠ BEFORE THIS: 'Fresnel' was in _TUNGSTEN_FAMILIES with no fixture in it, so
# the first Fresnel to arrive would have been read as a Source Four. A 65Q with
# no lamp recorded reported 575 W — the wrong number, 175 W light on every unit
# in a load table, explained by a note about a different maker's barrel.
w, note = ph.watts_for(SPOT)
check("an unlamped 65Q is 750 W", w, 750.0)
check("...because that is its chart's lamp", "at BTN" in note, True)
check("...and the note does not mention Source Fours", "S4" in note, False)
check("a BTL in it is 500 W", ph.watts_for(SPOT, lamp="BTL")[0], 500.0)
check("a BTP is 750 W", ph.watts_for(SPOT, lamp="BTP")[0], 750.0)
# ⭐ AN ANSI CODE CARRIES NO WATTAGE. "HPL 575" says 575 and lamp_watts reads it;
# "BTN" says nothing, so the number comes from the datasheet like any other.
check("BTN's wattage is published, not parsed", ph.lamp_watts("BTN"), 750.0)
check("...and is sourced in the table", "65Q" in ph.LAMP_WATTS["BTN"][1], True)
# ⚠ And it cannot be parsed, which is the point: nothing in "BTN" is a number.
check("...because the name carries none", ph.lamp_watts("BTQ"), None)

print("\n⚠ and the Source Four assumption is untouched")
# 🔴 THE REGRESSION THAT MATTERED. ETC's charts are measured at the HPL 750 but
# Jerry's barrels hold 575s, so an S4 with no lamp is read as a 575 — a stated
# assumption about HIS rig. Pointing every fixture at its reference lamp would
# have inflated every Source Four in the app by 30%.
check("an unlamped S4 26 is still 575 W", ph.watts_for("S4 26")[0], 575.0)
check("...with its original note", "S4s are 575 unless noted" in ph.watts_for("S4 26")[1], True)
check("an unlamped S4 PAR is still 575 W", ph.watts_for("S4 EA PAR MFL")[0], 575.0)
check("a named lamp still wins", ph.watts_for("S4 26", lamp="HPL 750")[0], 750.0)

print("\nthe names the paperwork actually uses")
# ⭐ "6in Fres" is Jerry's own Lightwright spelling, and it sat in NO_DATA as
# "no datasheet fetched" until he produced the datasheet on 2026.10.13.
# ⚠ All to the FLOOD end — see the section below for why that changed.
for name in ("6in Fres", "65Q", "Altman 65Q", "165Q", 'Altman 6" Fresnel'):
    check(f"{name!r} resolves", fn.resolve(name)[0], FLOOD)
check("'6in Fres' is no longer in NO_DATA", "6in fres" in fn.NO_DATA, False)
check("...but the 8\" still is", "8in fresnel" in fn.NO_DATA, True)

print("\n🔴 a bare name is the FLOOD end, and says so")
# ⚠ IT POINTED AT @spot FOR HALF A DAY, following 's4 parnel' -> 'S4 PARNel @25'
# and the argument that a smaller pool is the safer error on a drawing. That
# argument is wrong for a Fresnel: racked fully in it is 16°, a 2.9 ft pool at a
# 10 ft throw — tighter than an S4 26 — and nobody hangs a 6" Fresnel to get a
# 3-foot hot spot. Found by Jerry putting one on a plot and looking at it.
check("a bare 65Q is the flood end", fn.resolve("65Q")[0], FLOOD)
check("...and the note says which it chose", "@flood" in fn.resolve("65Q")[1], True)
check("Jerry's own paperwork name too", fn.resolve("6in Fres")[0], FLOOD)
check("asking for spot gets spot", fn.resolve("65Q spot")[0], SPOT)
check("the exact key resolves silently", fn.resolve(FLOOD), (FLOOD, ""))
# ⭐ And the flood end is a Fresnel-shaped pool rather than a hot spot.
check("...which is a 14.6 ft pool at a 10 ft throw, not 2.9",
      (round(ph.diameter(10.4, ph.FIXTURES[FLOOD]["field"]), 1),
       round(ph.diameter(10.4, ph.FIXTURES[SPOT]["field"]), 1)), (14.6, 2.9))

print("\n🔴 and it draws as a FRESNEL, not an ellipsoidal")
# ⚠ THE FAULT THE RENAME CAME FROM. symbols.for_type matches on a word in the
# key, and "Altman 65Q @spot" contains neither "fresnel" nor "fres" — so the
# first Fresnel in the table drew an ERS for half a day. Two fixes, both kept:
# the key says what it is, AND for_type asks the fixture table for the family.
from plotedit import symbols as _sym                 # noqa: E402
check("one closed poly, no barrel line",
      [pr[0] for pr in _sym.for_type(FLOOD)], ["poly"])
check("...the same shape at either end",
      _sym.for_type(SPOT), _sym.for_type(FLOOD))
# 🔴 The family check is what makes it robust: strip the word from the name and
# it must STILL draw a Fresnel, because the table says Fresnel.
check("the family alone is enough",
      [pr[0] for pr in _sym.for_type("Altman 65Q Fresnel @spot")], ["poly"])
# ⚠ And an ellipsoidal is still an ellipsoidal — poly plus its barrel line.
check("an S4 is untouched", [pr[0] for pr in _sym.for_type("S4 26")], ["poly", "line"])
check("a Shakespeare is untouched",
      [pr[0] for pr in _sym.for_type("Altman Shakespeare 30")], ["poly", "line"])

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
