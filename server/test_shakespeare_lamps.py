#!/usr/bin/env python3
"""The Altman Shakespeare's lamps, checked against its datasheet.

    cd server && python3 test_shakespeare_lamps.py

⭐ SOURCE: Altman Shakespeare 750W ellipsoidal datasheet (altmanlighting.com,
rev 111003), supplied by Jerry 2026.10.13. Closes #123.

🔴 WHY IT TOOK A SECOND COPY. `LAMP_MF` carried GLC alone, with a note saying the
sheet's other factors "do not line up cleanly enough to read them safely". The
clean copy reads perfectly — and then presents a different problem: **the
Correction Factor column prints 1.00 against GKV, and a DASH against the GLC,
which is the lamp the entire photometric chart was measured with.** Two baselines
on one page, apparently unconnected.

⭐ THE DETAIL THAT RESOLVES IT (Jerry, 2026.10.13: *"the GKV is probably for
Europe - its 230V"*). GKV is the GLC's 230-volt twin — 600 W/230 V, 15,000 lm,
3200 K, 400 hr against the GLC's 575 W/115 V, 15,500 lm, 3200 K, 400 hr. Its 1.00
means "on 230 V mains fit this and nothing changes"; the GLC's dash means "this
is the reference". The column IS anchored to the chart, and the factors transfer.

⚠ AND THEY CANNOT BE DERIVED. HX604 has the SAME 15,500 rated lumens as the GLC
and a factor of 1.14 — filament geometry, not output. No arithmetic recovers
these; only the sheet has them, which is why it was worth waiting for.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import photometrics as ph         # noqa: E402

FAILS = []
SHAKES = [f"Altman Shakespeare {d}" for d in (5, 10, 20, 30, 40, 50)]
S30 = "Altman Shakespeare 30"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("the performance chart, as the sheet prints it")
# ⭐ The first independent check these six have ever had — they went in from a
# reading of the same chart and nothing had confirmed them since.
SHEET = {"Altman Shakespeare 5":  (974900, 5, 7),
         "Altman Shakespeare 10": (791000, 7, 10),
         "Altman Shakespeare 20": (189700, 13, 20),
         "Altman Shakespeare 30": (149200, 18, 28),
         "Altman Shakespeare 40": (98100, 20, 38),
         "Altman Shakespeare 50": (46300, 23, 50)}
for k, (cd, beam, field) in SHEET.items():
    r = ph.FIXTURES[k]
    check(f"{k[-2:].strip()}° — cd, beam, field",
          (r["cd"], r["beam"], r["field"]), (cd, float(beam), float(field)))

print("\n⭐ five lamps now, where there was one")
check("offered, reference first", ph.lamps_for(S30),
      ["GLC", "GKV", "HX604", "HX400", "HX401"])
check("...the same five on every barrel",
      len({tuple(ph.lamps_for(k)) for k in SHAKES}), 1)

print("\nthe correction factors, straight off the sheet")
base = ph.footcandles(S30, 25.0, lamp="GLC")[0]
for lamp, mf in (("GLC", 1.00), ("GKV", 1.00), ("HX604", 1.14),
                 ("HX400", 0.69), ("HX401", 0.59)):
    check(f"{lamp} is {mf:.2f}",
          round(ph.footcandles(S30, 25.0, lamp=lamp)[0] / base, 4), round(mf, 4))
# ⭐ GKV is the GLC's 230 V twin, so it computes identically — that IS its 1.00.
check("GKV and GLC give the same light",
      ph.footcandles(S30, 25.0, lamp="GKV")[0],
      ph.footcandles(S30, 25.0, lamp="GLC")[0])
# ⚠ The reason the sheet is the only source: same lumens, different factor.
check("HX604 matches the GLC's 15,500 lm and is still 1.14",
      (ph.LAMP_WATTS["HX604"][0], round(ph.LAMP_MF["HX604"][S30], 2)), (575.0, 1.14))

print("\n🔴 and the four the sheet DASHES are not offered")
# Including both 750 W lamps, on a fixture the same page calls a 750 WATT
# SHAKESPEARE. Altman did not measure them; offering one would promise light
# nobody has measured.
for lamp in ("HX605", "GLA", "HX754", "HX755"):
    check(f"{lamp} is not offered", lamp in ph.lamps_for(S30), False)
    check(f"...and returns no figure", ph.footcandles(S30, 25.0, lamp=lamp)[0], None)

print("\n🔴 THE LOAD TABLE, which was wrong for every lamp but one")
# ⚠ Before today "Shakespeare" was not in _TUNGSTEN_FAMILIES, so watts_for fell
# through to FAMILY_WATTS and answered 575 W whatever was fitted. An HX754 and an
# HX400 on the same pipe both counted 575 — 175 W low and 200 W high, on the same
# circuit. It was right for the GLC and wrong for everything else, and nothing
# offered anything else until today, which is why it never showed.
for lamp, w in (("GLC", 575.0), ("GKV", 600.0), ("GLA", 575.0),
                ("HX400", 375.0), ("HX401", 375.0), ("HX604", 575.0),
                ("HX605", 575.0), ("HX754", 750.0), ("HX755", 750.0)):
    check(f"{lamp} draws {w:.0f} W", ph.watts_for(S30, lamp=lamp)[0], w)
# ⭐ A lamp with no multiplier still has a known LOAD. The footcandles stay blank
# and say why; the load table answers. Those are different facts.
check("HX754 has watts but no light",
      (ph.watts_for(S30, lamp="HX754")[0], ph.footcandles(S30, 25.0, lamp="HX754")[0]),
      (750.0, None))
# ⚠ An ANSI code carries no number — these cannot be parsed from the name.
check("GLC's wattage is published, not parsed", ph.lamp_watts("GLC"), 575.0)
check("...and sourced", "Altman Shakespeare" in ph.LAMP_WATTS["GLC"][1], True)

print("\nno lamp named still uses the chart's own lamp")
w, note = ph.watts_for(S30)
check("575 W, the GLC", w, 575.0)
check("...and it says which", "at GLC" in note, True)
check("...without claiming it is a Source Four", "S4" in note, False)

print("\n⚠ nothing else moved")
# 🔴 THE REGRESSION THAT WOULD MATTER. Adding Shakespeare to _TUNGSTEN_FAMILIES
# changes which path watts_for takes; ETC's barrels must be untouched.
check("an unlamped S4 26 is still 575 W", ph.watts_for("S4 26")[0], 575.0)
check("...with its own note", "S4s are 575 unless noted" in ph.watts_for("S4 26")[1], True)
check("an unlamped S4 PAR is still 575 W", ph.watts_for("S4 EA PAR MFL")[0], 575.0)
check("the 65Q still assumes its BTN at 750 W",
      ph.watts_for("Altman 65Q @spot")[0], 750.0)
check("a Lustr is still an LED, not a lamp", ph.lamps_for("Lustr 26 EDLT"), [])
check("no HPL reaches a Shakespeare",
      [l for l in ph.lamps_for(S30) if "HPL" in l], [])

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
