#!/usr/bin/env python3
"""A gel code is the same filter however it is punctuated.

    cd server && python3 test_gel_keys.py

🔴 gels.csv keys all 646 rows WITHOUT punctuation — R33, L142, G470. Plots and imported
paperwork commonly write the dashed form. A house rep plot read into plotedit came
in as R-37, L-142, R-54 and R-05, and every one missed the table.

⚠ IT FAILED HONESTLY, WHICH IS WHY NOBODY NOTICED. A missing gel returns no
factor and a note saying so, rather than a wrong number — so the plot simply had
no footcandle figure anywhere, for a fortnight, and nothing looked broken. On the
Big House sample that was 106 coloured units and not one transmission between
them.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import photometrics as ph     # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("the same filter, however it is written")
base = ph.gel_factor("R33")[0]
check("R33 is in the table", base is not None, True)
for form in ("R-33", "r-33", "R 33", "r33", "R–33"):
    check(f"{form!r} is the same filter", ph.gel_factor(form)[0], base)

print("\n⚠ but a bare number still has no maker")
# R33 is 65% and L33 is a different filter. Guessing a house's preferred maker is
# how a plot promises light it will not deliver.
f, note = ph.gel_factor("33")
check("33 does not resolve", f, None)
check("...and says why", "no maker" in note, True)

print("\n⚠ and something that is not a gel still is not one")
check("NC/Temp does not resolve", ph.gel_factor("NC/Temp")[0], None)

print("\n⭐ the note echoes what the USER wrote, not the normalised key")
# A reader checking a figure against their own paperwork needs to see their own
# spelling, or the note reads as being about a different filter.
check("R-33's note says R-33", "R-33" in ph.gel_factor("R-33")[1], True)

print("\n🔴 the sample that found it")
plot = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "samples", "Sample Big House.plot.json")))
coloured = [i for i in plot["instruments"] if (i.get("color") or "").strip()]
resolved = [i for i in coloured if ph.gel_factor(i["color"])[0] is not None]
check("units carrying a colour", len(coloured), 106)
# 🔴 Before the fix this was 0. The eight that still miss are NC/Temp, which is
# not a gel.
check("...and resolving to a transmission", len(resolved), 98)
check("every miss is NC/Temp, not a real gel",
      sorted({i["color"] for i in coloured if ph.gel_factor(i["color"])[0] is None}),
      ["NC/Temp"])

print("\n⚠ stacked and split frames normalise too")
check("a stacked pair", ph.gel_factor("R-33+R-54")[0] is not None, True)
check("...matches the undashed form",
      ph.gel_factor("R-33+R-54")[0], ph.gel_factor("R33+R54")[0])
check("a split frame", ph.gel_factor("R-33/R-54")[0], ph.gel_factor("R33/R54")[0])

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
