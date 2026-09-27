#!/usr/bin/env python3
"""Colour labels that would touch get pushed further out — issue #21.

    cd server && python3 test_labels_collide.py
"""
import json
import os
import sys

from fastapi.testclient import TestClient

from plotedit import labels
from plotedit.api import app

client = TestClient(app)
FAILS = []
SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "demo.plot.json")
demo = json.load(open(SAMPLE))["instruments"]

SCREEN = 0.5            # the browser draws the colour label 0.5 ft tall
PDF_QUARTER = 7 / 18    # 7pt at 1/4" = 1'-0"
PDF_EIGHTH = 7 / 9      # 7pt at 1/8"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def tiers_on(position, h, insts=None):
    insts = demo if insts is None else insts
    t = labels.color_tiers(insts, h)
    return [t[n] for n, i in enumerate(insts) if i.get("position") == position]


print("the width estimate, against a real measurement")
# ⭐ MEASURED IN THE BROWSER, not guessed: at font-size 0.5 (user units are
# feet) "R52+R119" has a bounding box 2.52 ft wide. If the estimate drifts far
# from that, every tier below is being decided on a fiction.
w = labels.color_width("R52+R119", 0.5)
check("R52+R119 at 0.5 ft reads about 2.5 ft wide", 2.3 < w < 2.7, True)

print("\nthe collision on the demo plot")
# 🔴 GRID C units 3 and 4 are 2'-6" apart where the rest of the pipe is 5'-6".
# The label is 2.52 ft wide, so the two ran together as "R52+R119R52+R119" —
# measured in the browser at -0.4px, i.e. actually overlapping.
check("on screen, one unit on GRID C is pushed out",
      tiers_on("GRID C", SCREEN), [0, 0, 0, 1, 0])
check("...and it is the close one, unit 4",
      [i["unit"] for i in demo if i.get("position") == "GRID C"][3], 4)

# ⚠ NO REGRESSION IN PRINT. At 1/4" the label is 7pt, which is 0.39 ft, and
# nothing on this plot collides — so no existing drawing may shift.
check("at 1/4\" on paper nothing moves", tiers_on("GRID C", PDF_QUARTER), [0, 0, 0, 0, 0])
check("at 1/8\" it collides and moves", tiers_on("GRID C", PDF_EIGHTH), [0, 0, 0, 1, 0])

print("\nthe rule itself")
def row(gap, text="R52+R119", n=3):
    return [{"unit": i + 1, "position": "E1", "color": text,
             "x": i * gap, "y": 20.0} for i in range(n)]

check("units far apart all stay at tier 0",
      labels.color_tiers(row(8.0), SCREEN), [0, 0, 0])
# ⭐ It comes BACK IN as soon as there is room. At 1'-6" spacing the third
# label clears the first, so it returns to tier 0 rather than marching outward
# for the length of the pipe — which is what a drafter does, and what stops a
# crowded batten growing a staircase of labels.
check("a label that clears again drops back to tier 0",
      labels.color_tiers(row(1.5), SCREEN), [0, 1, 0])
check("a unit with no colour is not tiered",
      labels.color_tiers([{"unit": 1, "position": "E1", "x": 0, "y": 0},
                          {"unit": 2, "position": "E1", "x": 0.1, "y": 0}], SCREEN), [0, 0])
# ⚠ Two units on DIFFERENT pipes are already a pipe apart; tiering them would
# push labels out for no reason.
check("neighbours on different positions are left alone",
      labels.color_tiers([{"unit": 1, "position": "E1", "color": "R80", "x": 0, "y": 20},
                          {"unit": 1, "position": "E2", "color": "R80", "x": 0, "y": 24}],
                         SCREEN), [0, 0])
# A boom's units share an x and differ in y — the rule has to sort along
# whichever axis the position actually runs, or every boom tiers itself.
check("a vertical position is measured along its own axis",
      labels.color_tiers([{"unit": i + 1, "position": "BOOM 1", "color": "R80",
                           "x": 2.0, "y": i * 8.0} for i in range(3)], SCREEN),
      [0, 0, 0])
check("...and a crowded one still tiers",
      labels.color_tiers([{"unit": i + 1, "position": "BOOM 1", "color": "R52+R119",
                           "x": 2.0, "y": i * 1.2} for i in range(3)], SCREEN),
      [0, 1, 2])
# A longer string needs more room than a short one at the same spacing.
check("a long colour string tiers where a short one does not",
      (labels.color_tiers(row(2.0, "R80"), SCREEN),
       labels.color_tiers(row(2.0, "R52+R119+R132"), SCREEN)),
      ([0, 0, 0], [0, 1, 2]))

print("\nthe server hands it to the browser")
r = client.post("/compute", json={"instruments": demo, "colorTextHeightFt": SCREEN})
check("/compute answers", r.status_code, 200)
rows = r.json()["instruments"]
check("...with a tier on every row", all("color_tier" in x for x in rows), True)
check("...matching the rule",
      [x["color_tier"] for x, i in zip(rows, demo) if i.get("position") == "GRID C"],
      [0, 0, 0, 1, 0])
# ⚠ The height is what makes it right for the caller's scale. Without it the
# server must not silently answer for some other drawing.
r2 = client.post("/compute", json={"instruments": demo, "colorTextHeightFt": PDF_QUARTER})
check("a different text height gives a different answer",
      [x["color_tier"] for x, i in zip(r2.json()["instruments"], demo)
       if i.get("position") == "GRID C"], [0, 0, 0, 0, 0])

print("\nthe sheet still draws")
import tempfile
from plotedit import exports
_plot = json.load(open(SAMPLE))
with tempfile.TemporaryDirectory() as d:
    for sc in ("1/4", "1/8"):
        out = os.path.join(d, "p.pdf")
        sheet, _ = exports.plot_pdf(_plot, out, scale=sc)
        check(f"a {sc}\" sheet renders", os.path.getsize(out) > 5000, True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
