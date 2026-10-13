#!/usr/bin/env python3
"""The section is reachable without a terminal, and it is worth reaching.

    cd server && python3 test_section.py

#92. `plot_to_section.py` has drawn a correct RP-2 §3 section since the scaffold
commit and shipped in every download. The only way to get one was:

    cd server && python3 plot_to_section.py yourplot.plot.json ../out/section.pdf

🔴 For an application whose whole premise is that it needs Python and nothing
else — double-click `run.command` and draw — that is not shipped. A beta tester
went looking for a section in the Export menu the day before this was written,
after being told one existed, and found nothing.

⭐ AND LOOKING AT THE OUTPUT FOUND A SECOND BUG, which is the half of this that
matters. A beam edge is projected to the floor; the shallow-angle guard only
skipped edges under 0.02 rad (1.1°), so a 2° edge from a 14-foot trim ran out to
roughly 400 feet. One such line stretched the drawing's extent to 93 feet for a
38-foot room, `fit` dropped a scale step to accommodate it, and the section came
out at 1/4" using 17% of an ARCH D sheet. Clipped to the room, the same plot
draws at 1/2".
"""
import io
import json
import os
import sys
import contextlib

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient            # noqa: E402
from plotedit.api import app                         # noqa: E402
from plot_to_section import render                   # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "..", "samples", "demo.plot.json")
PLOT = json.load(open(DEMO))
client = TestClient(app)


def quiet(fn, *a, **kw):
    """The renderer reports to stdout; the suite's own output stays readable."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return fn(*a, **kw)


print("the endpoint exists and returns a PDF")
r = client.post("/export/section", json={"plot": PLOT, "page": "ARCH_D"})
check("200", r.status_code, 200)
check("it is a PDF", r.headers.get("content-type"), "application/pdf")
check("named as a section", "Section.pdf" in r.headers.get("content-disposition", ""), True)
doc = pymupdf.open(stream=r.content, filetype="pdf")
text = doc[0].get_text()
check("one page", doc.page_count, 1)

print("\n§3 — the drawing says what it is")
# "Definition of where the section is cut" is required ON THE SHEET, which is
# what makes defaulting to centreline honest rather than a silent guess.
check("the title block states the cut",
      "cut on centerline" in text, True)
check("...and which way it looks", "looking stage left" in text, True)
check("the vertical zero is stated", "VERTICAL ZERO" in text, True)
check("a scaled luminaire is drawn, not a dot",
      "One luminaire per position" in text, True)

print("\n🔴 what it CANNOT prove is printed on it")
# The most valuable thing in the file, and the thing most likely to be lost when
# code moves behind a button.
check("the block is there", "NOT ON THIS DRAWING" in text, True)
check("masking is named", "Masking" in text, True)
check("...with who to ask", "ask the venue's rep plot or its TD" in text, True)
check("...and what it costs", "trims are NOT proven to clear" in text, True)
check("scenery is named", "Scenery in section" in text, True)
check("and it refuses to be read as a clearance check",
      "not a clearance check" in text, True)
# ⚠ The demo plot HAS a sight point, so that warning must NOT appear. A block
# that lists everything regardless would look identical in a screenshot.
check("the sight-point warning is absent, because the demo has one",
      "Audience sight point" in text, False)

print("\n⚠ a beam edge is clipped to the room, not projected to infinity")
sheet, drawn = quiet(render, DEMO, "/tmp/_sec_fit.pdf", page="ARCH_D")
x0, _, x1, _ = sheet._bounds
span_ft = (x1 - x0) / sheet.pt_per_ft
check("the drawing spans the room, not hundreds of feet", span_ft < 70, True)
# Before the clip this plot measured 93.0 feet and fit chose 1/4".
# ⭐ AND THEN 3/4", once the placement stopped reserving nine feet of pad on the
# left for a drawing that uses one (#94). This assertion read 1/2" for a
# fortnight: the plot fitted 3/4" the whole time and was being rejected for not
# fitting around a constant. 3/4" is 50% more drawing on the sheet whose entire
# purpose is reading trims off it.
check("so fit reaches 3/4\" on ARCH D", sheet.scale_label, "3/4\" = 1'-0\"")
# ⚠ And it is a real fit, not a bigger scale that clips — the next line checks
# that, and it is the half that matters.

print("\n🔴 the placement is measured, not reserved (#94)")
# The section set origin(ft(9), ft(3)) for every plot. Measured on three plots
# at every scale, the ink starts 1.00 ft left of the origin and 1.83 ft below —
# so eight of those nine feet were white paper, and the pad is in FEET, which
# means it scales: at 3/4" nine feet costs 6.75 inches of a 36-inch sheet.
import plot_to_section as _PS                              # noqa: E402
src = open(_PS.__file__, encoding="utf-8").read()
# ⚠ The CALL, not the string. `place_for`'s docstring quotes the old line so the
# next reader knows what this replaced, and that sentence is the reason nobody
# puts the constant back — so the check has to be able to tell the two apart.
check("no constant origin is called any more", "s.origin(ft(" in src, False)
check("it is placed from a measurement", "s.origin(*place)" in src, True)
check("...and the docstring still names what it replaced",
      "origin(ft(9), ft(3))" in src, True)

over_left = (sheet._bounds[0] - sheet.ox) / sheet.pt_per_ft
check("ink starts about a foot left of zero, as measured",
      round(over_left, 2), -1.0)
# ⭐ CENTRED, which the plot drawing learned in v0.1.22 and the section never
# did. Nothing left to take up means it is already where it should be.
check("...and there is no slack left to take up", round(sheet.slack_left(), 1), 0.0)
check("...in either axis", round(sheet.slack_above(), 1), 0.0)

print("\n⚠ a plot that genuinely needs a deep left pad still gets one")
# 🔴 THE REASON THE 9 WAS THERE. A sight point out in the seats is drawn at
# negative y, well left of the room. The old pad guessed at that case with a
# constant; this measures it. ⚠ foh_extent, which the issue also cited, has
# been deprecated and returning 0 since 2026.09.24 — the room is the whole room
# — so the sight point is the only deep-left case left.
deep = json.load(open(DEMO))
deep["room"] = dict(deep["room"]); deep["room"]["sightPoint"] = {"y": -30, "h": 3.5}
_dp = "/tmp/_sec_deep.plot.json"
json.dump(deep, open(_dp, "w"))
dsheet, _ = quiet(render, _dp, "/tmp/_sec_deep.pdf", page="ARCH_D")
deep_left = (dsheet._bounds[0] - dsheet.ox) / dsheet.pt_per_ft
check("the pad grows to what is drawn", round(deep_left), -30)
check("...and nothing is clipped",
      [w for w in dsheet.warnings if "CLIPPED" in w], [])
# ⚠ A wider drawing honestly takes a smaller scale. That is the guard working,
# not the pad failing.
check("...at the scale that honestly fits it", dsheet.scale_label, "1/2\" = 1'-0\"")
check("and nothing is clipped off the sheet",
      [w for w in sheet.warnings if w.startswith("CLIPPED")], [])

print("\nthe sheet is honoured, like any other drawing")
small = client.post("/export/section", json={"plot": PLOT, "page": "LETTER"})
check("a different sheet is accepted", small.status_code, 200)
# ⚠ This compared byte LENGTHS, and two different PDFs can be the same length —
# it failed on main depending on what text happened to be in the plot. The sheet
# is the thing that was asked for, so check the sheet.
import fitz as _fz
_big_w = _fz.open(stream=r.content, filetype="pdf")[0].rect.width
_small_w = _fz.open(stream=small.content, filetype="pdf")[0].rect.width
check("...and produces a different file", small.content != r.content, True)
check("...on the smaller sheet that was asked for", _small_w < _big_w, True)

print("\n🔴 an empty section is refused rather than drawn")
# A plot export with nothing on it is still worth having. A section of a room
# with no trims is a picture of an empty room, and returning one would read as
# the feature being broken.
bare = {"formatVersion": 1, "show": "Empty", "room": {"width": 30, "depth": 40},
        "positions": [], "instruments": []}
e = client.post("/export/section", json={"plot": bare})
check("422, not a blank PDF", e.status_code, 422)
check("...and it says what to do",
      "trim" in e.json().get("detail", "").lower(), True)

print("\nit is in the Export menu, which is the whole point of #92")
main_ts = open(os.path.join(HERE, "..", "web", "src", "main.ts"), encoding="utf-8").read()
api_ts = open(os.path.join(HERE, "..", "web", "src", "api.ts"), encoding="utf-8").read()
check("a menu entry exists", 'label: "Section"' in main_ts, True)
check("...wired to the export", 'runExport("section")' in main_ts, True)
check("...and the client knows the kind", '"section"' in api_ts, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
