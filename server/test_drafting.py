#!/usr/bin/env python3
"""Step 7: line weights, and the rulers along the edges of the plan.

    cd server && python3 test_drafting.py

⭐ WHY. RP-2 gives three line weights and the module picks the points for them:
heavy was 1.7pt, which is correct by the standard and reads as a heavy plot.
"The lines are too thick for pipes" was the report, and it was right.

⚠ THE TRAP THIS SUITE EXISTS FOR. A width override is only worth having if it
reaches EVERYTHING drawn at that weight. The first version changed the pipes and
left the instruments at full weight, because symbols.draw() read the module
constant instead of asking the sheet — the one place the mismatch is most
visible. Several assertions below exist only to catch that coming back.
"""
import contextlib
import io as _io
import json
import os
import sys
import tempfile

import fitz

from plotedit.scaled_pdf import (LINE_STYLES, HEAVY, Sheet, resolve_styles,
                                 _feet_label)
from plot_to_pdf import render

SAMPLE = os.path.join(os.path.dirname(__file__), "testdata", "blackbox.plot.json")
plot = json.load(open(SAMPLE))
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<56} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def widths(path):
    """How many strokes at each width are actually on the page."""
    out = {}
    for drawing in fitz.open(path)[0].get_drawings():
        w = round(drawing.get("width") or 0, 2)
        out[w] = out.get(w, 0) + 1
    return out


def sheet_for(name, **plot_keys):
    d = tempfile.mkdtemp()
    body = dict(plot)
    body.update(plot_keys)
    jp = os.path.join(d, "p.json")
    json.dump(body, open(jp, "w"))
    out = os.path.join(d, name + ".pdf")
    sh, _ = render(jp, out, scale="1/4")
    return sh, out


print("the three RP-2 weights can be dialled, and mean the same afterwards")
check("the standard puts a batten at 1.7pt", LINE_STYLES["batten"][0], HEAVY)
_t = resolve_styles({"heavy": 1.0})
check("dialling heavy moves the batten", _t["batten"][0], 1.0)
check("...and every other heavy line with it", _t["architecture"][0], 1.0)
check("...leaving light and medium alone", (_t["grid"][0], _t["masking"][0]),
      (LINE_STYLES["grid"][0], LINE_STYLES["masking"][0]))
# ⚠ The dash patterns are not overridable and must survive. A chain-dash IS the
# centre line; a plot that redefined it would be readable only by its author.
check("the centre line keeps its chain-dash", _t["centerline"][1],
      LINE_STYLES["centerline"][1])
check("the module table is not mutated", LINE_STYLES["batten"][0], HEAVY)
check("one named category can be moved alone",
      (resolve_styles({"styles": {"batten": 0.9}})["batten"][0],
       resolve_styles({"styles": {"batten": 0.9}})["architecture"][0]), (0.9, HEAVY))


def _refused(fn):
    try:
        fn()
    except KeyError:
        return True
    except Exception:
        return False
    return False


check("a category that does not exist is refused, not invented",
      _refused(lambda: resolve_styles({"styles": {"nonsense": 1.0}})), True)

print()
print("...and the override reaches the PAPER, not just the table")
_plain, _pp = sheet_for("plain")
_thin, _tp = sheet_for("thin", lineWeights={"heavy": 1.0})
_a, _b = widths(_pp), widths(_tp)
check("the default sheet is full of 1.7pt strokes", _a.get(1.7, 0) > 100, True)
# ⚠ THE ONE THAT CAUGHT THE REAL BUG. With symbols reading the module constant
# this number stayed above 200: the pipes went thin and every instrument stayed
# heavy. "Fewer" is not enough — almost none must be left.
check("dialling heavy leaves almost none of them", _thin and _b.get(1.7, 0) < 10, True)
check("...and they moved to the new weight", _b.get(1.0, 0) > _a.get(1.0, 0), True)

_per, _perp = sheet_for("per", lineWeights={"positions": {"electric": 0.7}})
_c = widths(_perp)
check("a position type can be given its own width", _c.get(0.7, 0) > 0, True)
check("...without moving anything else off heavy",
      abs(_c.get(1.7, 0) - _a.get(1.7, 0)) < _a.get(1.7, 0) * 0.1, True)

_s = Sheet(os.path.join(tempfile.mkdtemp(), "s.pdf"),
           weights={"positions": {"boom": 0.6}})
check("a type with no override keeps the category's width",
      _s.position_line("electric"), ("batten", None))
check("a type with one gets it", _s.position_line("boom"), ("batten", 0.6))
check("a catwalk is architecture, not a batten",
      _s.position_line("catwalk")[0], "architecture")

print()
print("the rulers: X along the bottom, Y up the side")
_r, _rp = sheet_for("rule", rulers=True)
_page = fitz.open(_rp)[0]
_text = _page.get_text()
check("both axes are named on the sheet",
      ("X — ACROSS" in _text, "Y — UPSTAGE" in _text), (True, True))
check("ticks are labelled in feet", "12'" in _text, True)

# ⚠ WHICH EDGE CARRIES WHICH AXIS is the whole point, and a suite that only
# checked the captions EXIST would pass with them swapped. Find where each one
# was actually drawn. fitz measures y DOWNWARD from the top of the page, so the
# bottom of the drawing is the LARGER y.
def _where(needle):
    for b in _page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                if needle in sp["text"]:
                    return sp["bbox"]
    return None


_x_at, _y_at = _where("ACROSS"), _where("UPSTAGE")
check("both captions were placed", bool(_x_at and _y_at), True)
check("X is BELOW Y on the page — it is the bottom ruler",
      _x_at[3] > _y_at[3], True)
check("Y is LEFT of X — it is the side ruler", _y_at[0] < _x_at[0], True)

_no = widths(_pp)
check("a plot that does not ask for rulers does not get them",
      "ACROSS" in fitz.open(_pp)[0].get_text(), False)

# The rulers sit OUTSIDE the room, so the sheet has to be sized to include them
# — otherwise they are the one thing guaranteed to fall off the edge.
check("the rulers are inside the drawing's own bounds",
      [w for w in _r.warnings if w.startswith("CLIPPED")], [])

print()
print("tick labels read as feet and inches, and keep their sign")
for _v, _want in ((0, "0'"), (12, "12'"), (7.25, "7'-3\""), (-11.5, "-11'-6\"")):
    check(f"{_v} reads as {_want}", _feet_label(_v), _want)


print()
print("the scale bar stays on the paper, at every scale")
# 🔴 It did not. The bar was always TEN divisions of one unit, and when a
# division became a metre that made it 15.75 inches long at 1:25 — through the
# title block and off the right-hand edge, with the last label not on the page.
#
# ⚠ Nothing caught it because the bar is drawn in PAGE POINTS, not through P().
# The clipping guard only knows what the drawing touched, so furniture can walk
# off the sheet without it ever being asked. Hence this test measures the
# rendered rectangles rather than trusting the arithmetic that placed them.
from plotedit.scaled_pdf import fit_scales as _fits
from plotedit import units as _u

def _bar_extent(path):
    """(left, right) of the scale bar's run of little rectangles, in points."""
    page = fitz.open(path)[0]
    runs = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "re":
                r = item[1]
                if 4.0 < r.height < 7.0 and r.width > 8.0:
                    runs.append((r.x0, r.x1))
    return (min(x0 for x0, _ in runs), max(x1 for _, x1 in runs)) if runs else None


_checked = 0
for _sys in (_u.IMPERIAL, _u.METRIC):
    for _sc in _fits(_sys):
        _d = tempfile.mkdtemp()
        _body = dict(plot)
        if _sys == _u.METRIC:
            _body["units"] = "metric"
        _jp = os.path.join(_d, "p.json")
        json.dump(_body, open(_jp, "w"))
        _out = os.path.join(_d, "p.pdf")
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            _sheet, _ = render(_jp, _out, scale=_sc)
        _page = fitz.open(_out)[0]
        _ext = _bar_extent(_out)
        _ok = _ext is not None and _ext[0] >= 0 and _ext[1] <= _page.rect.width
        if not _ok:
            check(f"{_sc}: the scale bar is on the page", (_ext, _page.rect.width), "on it")
        _checked += 1
        _divs, _step, _total, _per = _sheet.scale_bar_plan()
        if _divs < 2:
            check(f"{_sc}: at least two divisions", _divs, ">= 2")
        if _total > 4.2 * 72:
            check(f"{_sc}: the bar is a readable length", round(_total / 72, 2), "<= 4.2 in")

check(f"every scale in both ladders drawn and measured ({_checked})", _checked, 11)
check("...and none of them put the bar off the sheet", True, True)


# ------------------------------------------- a position label is read, not lost
print("\na position label knocks out what is under it")
# 🔴 Issue #66. Now that an imported base plan prints, a position name can have
# the venue's own walls drawn straight through it. On a real plan, 42 words on
# the sheet had a line running through them, including the leading letter of
# ELECTRIC 1. It is not a placement error — the pipe runs wall to wall and the
# label sits at its stage-left end, which is exactly where the wall is.
#
# ⭐ MEASURED BY RASTERISING, because the fix does not remove the line — it
# paints over it. Counting geometry still finds the line and always will; the
# question is what reaches the eye. So: a label over a base plan must look the
# same as a label over nothing.
import json as _j
import tempfile as _t
import pymupdf as _mu2
from PIL import Image as _Im
import plot_to_pdf as _P2

_LP = {"formatVersion": 1, "show": "T", "venue": "v", "designer": "d",
       "studio": "s", "room": {"width": 30, "depth": 20},
       "positions": [{"name": "ELECTRIC 1", "type": "electric",
                      "x1": 0, "y1": 10, "x2": 30, "y2": 10, "trim": 14}],
       "instruments": []}
# A comb, which is what a ground plan actually looks like where a label lands.
_WALLS = {"paths": [{"layer": "W", "points": [[n / 4.0, 0], [n / 4.0, 20]]}
                    for n in range(1, 13)]}


def _label_ink(base):
    """Dark pixels inside the ELECTRIC label's own box."""
    with _t.TemporaryDirectory() as d:
        pj = os.path.join(d, "p.json")
        _j.dump(_LP, open(pj, "w"))
        f = os.path.join(d, "o.pdf")
        _P2.render(pj, f, scale="1/2", page="ARCH_C", base=base)
        pg = _mu2.open(f)[0]
        w = [x for x in pg.get_text("words") if x[4] == "ELECTRIC"][0]
        z = 6
        pix = pg.get_pixmap(matrix=_mu2.Matrix(z, z))
        im = _Im.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        box = im.crop((int(w[0] * z), int(w[1] * z), int(w[2] * z), int(w[3] * z)))
        return sum(1 for v in box.getdata() if v < 128)


_clear = _label_ink(None)
_over = _label_ink(_WALLS)
_extra = 100.0 * (_over - _clear) / _clear
check("the label prints at all", _clear > 500, True)
# ⚠ Not zero. The knockout's edge and the antialiasing either side of it leave a
# little, and a threshold of exactly zero would be a test that fails on a font
# update rather than on a regression. Without the knockout this comb gives 12%.
#
# ⚠ THE NUMBER IN THIS COMMENT IS THE COMB'S. An earlier draft of the test used
# three walls instead of twelve and measured 3.8%, and that figure was left here
# when the comb replaced it — a stale number beside a live one, which Copilot
# caught on #67. The threshold is what the test enforces; the percentages are
# here to say how much room it has, so they have to be of the same thing.
check("a label over a base plan reads like one over nothing",
      _extra < 2.0, True)
print(f"       ({_clear} px clear, {_over} px over twelve walls, +{_extra:.1f}%)")


# ⚠ And the knockout must NOT reach the DXF. There the text is on its own layer
# and the reader turns layers off, so a white rectangle exported beside it would
# be an object nobody asked for. Checked by COUNTING PER LABEL rather than by
# looking for white: if each label brought a fill along, five positions would
# bring five more than one does.
def _dxf_fills(n_positions):
    with _t.TemporaryDirectory() as d:
        plot = dict(_LP)
        plot["positions"] = [{"name": f"ELECTRIC {i}", "type": "electric",
                              "x1": 0, "y1": 2 + i * 2, "x2": 30, "y2": 2 + i * 2,
                              "trim": 14} for i in range(1, n_positions + 1)]
        pj = os.path.join(d, "p.json")
        _j.dump(plot, open(pj, "w"))
        dxf = os.path.join(d, "o.dxf")
        _P2.render(pj, os.path.join(d, "o.pdf"), scale="1/2", page="ARCH_C", dxf=dxf)
        t = open(dxf).read()
        return t.count("\nSOLID\n") + t.count("\nHATCH\n"), t.count("ELECTRIC")


_f1, _t1 = _dxf_fills(1)
_f5, _t5 = _dxf_fills(5)
check("the DXF carries every position name", (_t1, _t5), (1, 5))
check("...and not one fill per label", _f5, _f1)


# 🔴 AND THE NAMES MUST GO ON LAST. A knockout can only clear what is ALREADY on
# the canvas, so a label drawn with the pipes is repainted by anything that
# comes after it — a pool, or a later position crossing an earlier one. Copilot
# found this on #67 and it was real: drawing one line after a knocked-out label
# brought 2898 of its pixels back. plot_to_pdf now holds the names until every
# pool and pipe is down.
def _label_vs_later_geometry():
    """Pixels of a knocked-out label that a pool repaints. Zero is the answer."""
    _unit = {"unit": 1, "channel": 1, "type": "S4 26", "x": 5.5, "y": 20,
             "trim": 14, "focusX": 8, "focusY": 10, "color": "R80",
             "position": "GRID C"}
    plot = {"formatVersion": 1, "show": "T", "venue": "v", "designer": "d",
            "studio": "s", "room": {"width": 30, "depth": 26},
            "positions": [{"name": "GRID C", "type": "electric",
                           "x1": 0, "y1": 20, "x2": 30, "y2": 20, "trim": 14},
                          # its name lands inside the pool below
                          {"name": "ELECTRIC 1", "type": "electric",
                           "x1": 7.0, "y1": 8.7, "x2": 30, "y2": 8.7, "trim": 14}],
            "instruments": [_unit]}
    shot = {}
    for pools in (False, True):
        with _t.TemporaryDirectory() as d:
            pj = os.path.join(d, "p.json")
            _j.dump(plot, open(pj, "w"))
            f = os.path.join(d, "o.pdf")
            _P2.render(pj, f, scale="1/2", page="ARCH_D", show_pools=pools)
            pg = _mu2.open(f)[0]
            w = [x for x in pg.get_text("words") if x[4] == "ELECTRIC"][0]
            z = 8
            pix = pg.get_pixmap(matrix=_mu2.Matrix(z, z))
            im = _Im.frombytes("RGB", (pix.width, pix.height),
                               pix.samples).convert("L")
            shot[pools] = im.crop((int(w[0] * z), int(w[1] * z),
                                   int(w[2] * z), int(w[3] * z)))
    from PIL import ImageChops as _IC
    return sum(1 for v in _IC.difference(shot[False], shot[True]).getdata() if v > 8)


check("a pool drawn later does not reach the label", _label_vs_later_geometry(), 0)

# ⚠ And the mechanism itself, with no plot in the way: a knockout protects
# against what is BEFORE it and nothing else. This is the test that has to keep
# working, because it is the reason the names are deferred at all.
def _knockout_vs_after():
    from plotedit.scaled_pdf import Sheet as _S
    out = []
    for after in (False, True):
        with _t.TemporaryDirectory() as d:
            f = os.path.join(d, "o.pdf")
            sh = _S(f, page="ARCH_C", scale="1/2", landscape=True)
            sh.origin(5, 5)
            sh.line(0, 10, 30, 10, style="batten")
            sh.text(1, 10, "ELECTRIC 1", size=7, bold=True, knockout=True)
            if after:
                sh.line(0, 10.05, 30, 10.05, style="batten")
            sh.finish()
            pg = _mu2.open(f)[0]
            w = [x for x in pg.get_text("words") if x[4] == "ELECTRIC"][0]
            z = 8
            pix = pg.get_pixmap(matrix=_mu2.Matrix(z, z))
            im = _Im.frombytes("RGB", (pix.width, pix.height),
                               pix.samples).convert("L")
            out.append(im.crop((int(w[0] * z), int(w[1] * z),
                                int(w[2] * z), int(w[3] * z))))
    from PIL import ImageChops as _IC
    return sum(1 for v in _IC.difference(out[0], out[1]).getdata() if v > 8)


check("a knockout does NOT protect against what comes after it",
      _knockout_vs_after() > 50, True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
