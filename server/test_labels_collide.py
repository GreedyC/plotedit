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
# 🔴 THE BOOM FOOTNOTE IS ONE SENTENCE FOR THE WHOLE STRIP. It used to be drawn
# once per boom, centred on that boom's own pipe, so two booms standing near
# each other overprinted it and neither copy was readable. Found on a tester's
# export, 2026.09.30 — the words "NOT TO SCALE" sat on top of "heights", and
# "1 break" on top of "compressed".
# 🔴 samples/demo.plot.json, NOT plots/sample.plot.json. The plots folder is
# GITIGNORED — it holds the designer's own saved work — so a test that reads
# from it passes on the machine that wrote it and fails in CI on a checkout
# that has never had one. Caught by CI, 2026.09.30, not by any local run.
print("\nthe boom footnote is drawn once, not once per boom")
import pymupdf as _mu
from fastapi.testclient import TestClient as _TC
from plotedit.api import app as _app
_c = _TC(_app)
_plot = json.load(open(os.path.join(os.path.dirname(__file__), "..", "samples",
                                    "demo.plot.json"), encoding="utf-8"))


def _overlaps(page, scale):
    r = _c.post("/export/pdf", json={"plot": _plot, "page": page, "scale": scale})
    if r.status_code != 200:
        return None
    pg = _mu.open(stream=r.content, filetype="pdf")[0]
    ws = pg.get_text("words")
    out = []
    for i in range(len(ws)):
        for j in range(i + 1, len(ws)):
            a = _mu.Rect(ws[i][0], ws[i][1], ws[i][2], ws[i][3])
            b = _mu.Rect(ws[j][0], ws[j][1], ws[j][2], ws[j][3])
            x = a & b
            if x.is_valid and x.get_area() > 0.45 * min(a.get_area(), b.get_area()):
                out.append((ws[i][4], ws[j][4]))
    return out, pg.get_text()


_hits, _txt = _overlaps("ARCH_C", "1/8")
check("the note appears once", _txt.count("NOT TO SCALE — heights are the data"), 1)
check("...and so does the compression note", _txt.count("pipes compressed"), 1)
check("...which counts the pipes", "2 of 2 pipes compressed" in _txt, True)
# ⚠ The exact pairs that were overprinting. Named, so a regression says which.
check("NOT TO SCALE no longer collides",
      [h for h in _hits if "NOT" in h or "SCALE" in h], [])
check("the break note no longer collides",
      [h for h in _hits if "compressed" in h or "break" in h], [])

# ⚠ WHAT IS LEFT IS SCALE-DEPENDENT, and it is recorded rather than asserted
# away — see docs/NEXT.md. The plan labels are spaced in FEET, so the smaller
# the scale the closer they sit on paper. This pins the direction, not a number
# that would go stale the first time a label moves.
_eighth = len(_overlaps("ARCH_C", "1/8")[0])
_half = len(_overlaps("ARCH_D", "1/2")[0])
check("a half-inch plot has no colliding labels", _half, 0)
check("...and 1/8\" is worse than 1/2\"", _eighth >= _half, True)


# ⭐ THE DRAWING IS CENTRED ON THE SHEET, not parked on the bottom margin.
# From Jerry's own exports, 2026.09.30: 2.63" of white above and 0.50" below on
# Letter. The origin in plot_to_pdf is a FLOOR — it pads for the FOH catwalk and
# the booms so neither is clipped off the bottom — and nothing asked what was
# left over above.
print("\nthe drawing is centred on the sheet")
import plot_to_pdf as _P
import tempfile as _tfd


def _white(page, lift):
    with _tfd.TemporaryDirectory() as d:
        f = os.path.join(d, "x.pdf")
        _P.render(os.path.join(os.path.dirname(__file__), "..", "samples",
                               "demo.plot.json"),
                  f, scale="fit", page=page, lift=lift)
        pg = _mu.open(f)[0]
        H = pg.rect.height
        bb = _mu.Rect(1e9, 1e9, -1e9, -1e9)
        for dr in pg.get_drawings():
            if dr["rect"].get_area() > 0.80 * pg.rect.get_area():
                continue
            bb |= dr["rect"]
        for w in pg.get_text("words"):
            bb |= _mu.Rect(w[0], w[1], w[2], w[3])
        return bb.y0 / 72, (H - bb.y1) / 72


for _pg in ("LETTER", "TABLOID", "ARCH_C", "ARCH_D"):
    _b_above, _ = _white(_pg, 0.0)
    _a_above, _ = _white(_pg, None)
    check(f"{_pg} wastes less at the top", round(_a_above, 2) <= round(_b_above, 2), True)

# 🔴 ARCH D was ALREADY near-centred, and the first attempt at this pushed it
# 0.44" off. Named because a regression there is the one that would look like an
# improvement everywhere else.
_d_before, _ = _white("ARCH_D", 0.0)
_d_after, _ = _white("ARCH_D", None)
check("ARCH D is not made worse", _d_after <= _d_before + 0.01, True)

# ⚠ And centring must never create a clipping warning. The lift is clamped out
# of the band finish() polices, so a drawing that fitted still fits.
with _tfd.TemporaryDirectory() as _d:
    _s, _ = _P.render(os.path.join(os.path.dirname(__file__), "..", "samples",
                                   "demo.plot.json"),
                      os.path.join(_d, "x.pdf"), scale="fit", page="LETTER")
    check("centring raises no CLIPPED warning",
          [w for w in _s.warnings if "CLIPPED" in w], [])



# ------------------------------------------------- the key keeps out of the way
print("\nthe instrument key stays clear of the drawing")
import json as _json

_DEMO = os.path.join(os.path.dirname(__file__), "..", "samples", "demo.plot.json")

# Words the key prints. Enough of them to catch a line crossing anywhere in the
# block, and all distinctive enough not to appear in the drawing itself.
_KEY_WORDS = {"INSTRUMENT", "KEY", "NOTATION", "COLOR", "ACCESSORIES",
              "hexagon", "rectangle", "circle"}


def _struck(base):
    """Key labels that a LONG line passes through.

    🔴 The defect: a base plan offset ten feet ran its walls through "6) S4 26"
    and four lines of NOTATION and read as a strikethrough. The clipping guard
    never saw it, because the guard polices the sheet EDGE and the key sits
    nowhere near the edge.

    ⚠ The key draws its own little fixture symbols, so "nothing overlaps the
    key" would fail on the key itself. A strikethrough is a LONG line — the
    discriminator is width. A symbol is a third of an inch; a venue wall at 3/8"
    is a foot of paper.
    """
    with _tfd.TemporaryDirectory() as d:
        f = os.path.join(d, "k.pdf")
        _P.render(_DEMO, f, scale="3/8", base=base)
        pg = _mu.open(f)[0]
        # ⚠ A path's rect is its BOUNDING BOX, so the sheet border alone would
        # "intersect" every word on the page. A strikethrough is long AND thin:
        # two inches across, under two points tall.
        lines = [dr["rect"] for dr in pg.get_drawings()
                 if (dr["rect"].x1 - dr["rect"].x0) > 144
                 and (dr["rect"].y1 - dr["rect"].y0) < 2]

        # 🔴 NOT Rect & Rect. A horizontal line has ZERO HEIGHT, so its
        # intersection with anything has zero AREA and an area test can never
        # fire — which is exactly how the first version of this passed with the
        # fix reverted. Ask the question geometrically instead: does the line
        # span the word horizontally, at a height inside the word's own box.
        def crossed(w):
            return any(ln.x0 < w[2] and ln.x1 > w[0] and w[1] <= ln.y0 <= w[3]
                       for ln in lines)

        words = [w for w in pg.get_text("words") if w[4] in _KEY_WORDS]
        return sorted({w[4] for w in words if crossed(w)}), len(words)


# ⚠ The base plan is built HERE rather than read from a .dxf, because *.dxf is
# gitignored and a test that quietly skips on CI is a test that is not run.
#
# 🔴 AND IT IS A COMB, not the room's outline, which is the version that taught
# me this. A horizontal line only strikes a word if it lands on that word's own
# 7pt row, so three walls at three heights sailed between the key's lines and
# the test passed with the fix REVERTED. A line every foot cannot miss.
_ROOM = _json.load(open(_DEMO))["room"]
_W, _D = _ROOM["width"], _ROOM["depth"]
_off = {"paths": [{"layer": "WALL",
                   "points": [[10, 4 + n], [10 + _W, 4 + n]]}
                  for n in range(0, int(_D) + 1)]}
_hit_plain, _n = _struck(None)
_hit_base, _ = _struck(_off)
check("the key prints its labels at all", _n > 0, True)
check("nothing strikes the key with no base plan", _hit_plain, [])
check("...nor with one offset ten feet", _hit_base, [])

# ⭐ And the rule underneath it, tested directly: the key is placed clear of what
# is ACTUALLY drawn, not of the room. Pools are the thing that reaches past the
# room on an ordinary plot, so turning them on must move the key.
from plotedit import scaled_pdf as _SP

_reach = {}
_orig_dr = _SP.Sheet.drawn_right_ft


def _spy(self):
    v = _orig_dr(self)
    _reach[id(self)] = v
    return v


_SP.Sheet.drawn_right_ft = _spy
try:
    with _tfd.TemporaryDirectory() as _d:
        _reach.clear()
        _P.render(_DEMO, os.path.join(_d, "a.pdf"), scale="1/2", show_pools=False)
        _no_pools = max(_reach.values())
        _reach.clear()
        _P.render(_DEMO, os.path.join(_d, "b.pdf"), scale="1/2", show_pools=True)
        _with_pools = max(_reach.values())
finally:
    _SP.Sheet.drawn_right_ft = _orig_dr

check("with pools off the key clears the room wall",
      round(_no_pools, 1), round(_json.load(open(_DEMO))["room"]["width"], 1))
check("pools push it further out", _with_pools > _no_pools + 1, True)

# ---------------------------------------------- centred the other way round too
print("\nthe drawing is centred left to right")


def _sides(page, shift):
    """The drawing's own margins, left and right, in inches.

    ⚠ Measured from the sheet's bounds, NOT from the PDF's ink. The title block
    and the scale bar are page furniture — drawn in page points at a fixed
    corner, never through P() — so a bbox of everything on the page is pinned to
    the title block at the right and reports a centred drawing as lopsided. The
    first version of this test did exactly that and called ARCH D's genuine
    improvement a regression.
    """
    with _tfd.TemporaryDirectory() as d:
        sh, _ = _P.render(_DEMO, os.path.join(d, "x.pdf"), scale="fit",
                          page=page, shift=shift)
        x0, _, x1, _ = sh._bounds
        m = sh.margin
        return (x0 - m) / 72.0, (sh.page_pt[0] - m - x1) / 72.0


# 🔴 Measured on the demo plot at 1/2": 4.21' of dead paper against the left
# margin while 3.03' hung off the RIGHT — with 1.18' of slack going spare. The
# vertical axis was fixed on 2026.09.30; the horizontal had never been measured.
for _pg in ("LETTER", "TABLOID", "ARCH_C", "ARCH_D"):
    _l0, _r0 = _sides(_pg, 0.0)
    _l1, _r1 = _sides(_pg, None)
    check(f"{_pg} is more even side to side",
          round(abs(_l1 - _r1), 2) <= round(abs(_l0 - _r0), 2) + 0.01, True)

# ⚠ And it must never create a clipping warning, the same clamp the lift has.
with _tfd.TemporaryDirectory() as _d:
    _s2, _ = _P.render(_DEMO, os.path.join(_d, "x.pdf"), scale="fit", page="ARCH_D")
    check("side-to-side centring raises no CLIPPED warning",
          [w for w in _s2.warnings if "CLIPPED" in w], [])

if FAILS:


    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
