#!/usr/bin/env python3
"""Step 3's condition: the screen and the paper must agree.

The browser asks the API. The PDF calls scaled_pdf. Both start from the same
.plot.json, so every number must match — and when they did not, it was because
scaled_pdf.unit() had no `mode` parameter and quietly computed LED fixtures at
their reference output instead of the mode the plot asked for. 441 fc where the
answer was 382.

    cd server && python3 test_agreement.py
"""
import json
import os
import sys

from fastapi.testclient import TestClient

from plotedit.api import app
from plot_to_pdf import render

SAMPLE = os.path.join(os.path.dirname(__file__), "testdata", "blackbox.plot.json")
OUT = os.path.join(os.path.dirname(__file__), "..", "out", "agreement.pdf")

plot = json.load(open(SAMPLE))

# --- what the browser gets
client = TestClient(app)
api_rows = client.post("/compute", json={"instruments": [
    {"unit": i["unit"], "channel": i.get("channel"), "type": i["type"],
     "x": i["x"], "y": i["y"], "trim": i.get("trim"),
     "focus_x": i.get("focusX"), "focus_y": i.get("focusY"),
     "focus_h": i.get("focusH", 5.5), "color": i.get("color"),
     "lamp": i.get("lamp"), "mode": i.get("mode")}
    for i in plot["instruments"]
]}).json()["instruments"]

# --- what the PDF gets
os.makedirs(os.path.dirname(OUT), exist_ok=True)
_, pdf_rows = render(SAMPLE, OUT)

fails = []
print(f"{'ch':<5} {'type':<15} {'API throw':<11} {'PDF throw':<11} {'API fc':>7} {'PDF fc':>7}")
for a, p in zip(api_rows, pdf_rows):
    if not a["computed"]:
        continue
    at, pt = round(a["throw"], 2), round(p["throw"], 2)
    af = round(a["footcandles"]) if a["footcandles"] else None
    pf = round(p["fc"]) if p.get("fc") else None
    ok = at == pt and af == pf
    print(f"{str(a['channel'] or ''):<5} {a['type']:<15} {at:<11} {pt:<11} "
          f"{str(af):>7} {str(pf):>7}  {'' if ok else '  <-- DISAGREE'}")
    if not ok:
        fails.append(f"ch {a['channel']}: API {at}ft/{af}fc vs PDF {pt}ft/{pf}fc")

    ap, pp = a.get("field"), p.get("field")
    if ap and pp and round(ap, 2) != round(pp, 2):
        fails.append(f"ch {a['channel']}: pool {ap} vs {pp}")

print(f"screen and paper agree on all {len(pdf_rows)} instruments")


# ---------------------------------------------------------------------------
print("\nthe 90-degree display option is COSMETIC")
# RP-2 p.2: "It is acceptable to visually orient the angle of each drawn
# luminaire to either focus points or 90° axes." Jerry, 2026.09.23: "most plots
# display the instruments on even 90 degree mounts... even though the lamp may
# be actually pointing 320 degrees, it would be displayed as 0 degrees."
#
# 🔴 The whole risk of that option is that it leaks into the arithmetic. A unit
# DRAWN at 0 while pointing at 320 is a drawing convention; a unit COMPUTED at 0
# would be a lie about where the light lands. So the same plot rendered both
# ways must produce identical numbers.
import json as _json
from plotedit.scaled_pdf import Sheet as _S
import plot_to_pdf as _p2p

_plot = _json.load(open("testdata/blackbox.plot.json"))

def _numbers(mode):
    import tempfile, os
    _plot["symbolAngle"] = mode
    path = os.path.join(tempfile.mkdtemp(), f"{mode}.pdf")
    _json.dump(_plot, open(path + ".json", "w"))
    sheet, rows = _p2p.render(path + ".json", path, scale="1/4",
                              page="ARCH_D", landscape=True)
    return [(r["num"], round(r["throw"], 4), round(r["pan"], 4),
             round(r.get("fc") or 0, 4)) for r in rows if r]

_ortho = _numbers("orthogonal")
_focus = _numbers("focus")
if len(_ortho) < 5:
    fails.append("too few units to compare the two display modes")
if _ortho != _focus:
    for a, b in zip(_ortho, _focus):
        if a != b:
            fails.append(f"unit {a[0]}: orthogonal {a[1:]} vs focus {b[1:]} — the "
                         f"90-degree DISPLAY option has leaked into the arithmetic")
else:
    print(f"  ok   both display modes give identical numbers for {len(_ortho)} units")

# ---------------------------------------------------------------- notation
# ⭐ The screen and the paper must agree about WHERE a label goes, not only
# about the numbers on it. They agreed on every figure and still drew different
# pictures three times in one day: the unit number, the trims, the throw and fc.
#
# The rule, RP-2 §6.14.2 and Jerry 2026.09.24: "the channel number should be
# behind the light, not in front. The colour label should be along the width of
# the lens in the front." Front and back belong to the INSTRUMENT — 0° points
# toward -y, so a fixed page offset is wrong for three quarters of a rig.
#
# The browser's half of this is `notationAnchor` in web/src/geometry.ts, tested
# the same way in geometry.test.ts. If you change one, change both.
from plotedit import symbols as _sym

class _Rec:
    """A sheet that records text instead of drawing it."""
    def __init__(self): self.t = []
    def text(self, x, y, s, **k): self.t.append((str(s), x, y))
    def line(self, *a, **k): pass
    def rect(self, *a, **k): pass
    def circle(self, *a, **k): pass

print()
for _name, _deg, _fx, _fy in [("downstage", 0, 0, -1), ("upstage", 180, 0, 1),
                              ("stage right", 90, 1, 0), ("stage left", 270, -1, 0)]:
    _r = _Rec()
    _sym.notation(_r, 0, 0, channel=12, circuit=34, color="R33", unit=3, rotate_deg=_deg)
    _at = dict((s, (x, y)) for s, x, y in _r.t)
    _c, _h = _at.get("R33"), _at.get("12")
    if not _c or not _h:
        fails.append(f"aimed {_name}: notation drew no colour or no channel")
        continue
    # Positive dot with the front vector means in front of the lens.
    _cd = _c[0] * _fx + _c[1] * _fy
    _hd = _h[0] * _fx + _h[1] * _fy
    ok = _cd > 0.5 and _hd < -0.5
    print(f"  {'ok  ' if ok else 'FAIL'} aimed {_name:<12} colour {_cd:+.2f} ahead, "
          f"channel {_hd:+.2f}")
    if not ok:
        fails.append(f"aimed {_name}: colour {_cd:+.2f} / channel {_hd:+.2f} — colour "
                     f"must be in FRONT (+) and the channel BEHIND (-)")

# ---------------------------------------------------------------- booms
# 🔴 A boom's units are drawn in ELEVATION and NOT in plan — in plan a boom is a
# point, and drawing them there stacked three symbols and three channel circles
# on one spot. The danger in skipping them is that a unit missing from the
# elevation now appears on NO drawing at all, silently. So: every unit on a
# vertical position must appear in exactly one elevation, and its labelled
# height must be its real height — compression moves ink, never numbers.
from plotedit import booms as _bm
from plotedit import positions as _PP

print()
_verts = [p for p in plot["positions"] if _PP.is_vertical(p)]
_on_booms = [i for i in plot["instruments"]
             if (i.get("position") or "").strip().lower()
             in {(p.get("name") or "").strip().lower() for p in _verts}]
_lay = _bm.layout(plot["positions"], plot["instruments"])
_drawn = [(b["name"], u) for b in _lay for u in b["units"]] \
       + [(b["name"], u) for b in _lay for u in b["no_height"]]

if len(_drawn) != len(_on_booms):
    fails.append(f"{len(_on_booms)} units hang on booms but {len(_drawn)} are drawn — "
                 f"the rest are on NO drawing, because plan skips them")
else:
    print(f"  ok   all {len(_on_booms)} boom units appear in an elevation")

_by_unit = {(  (i.get("position") or "").strip().lower(), i.get("unit")): i
            for i in _on_booms}
for b in _lay:
    for u in b["units"]:
        real = next((i for i in _on_booms if i.get("unit") == u["unit"]
                     and (i.get("position") or "").upper() == b["name"]), None)
        if real is None:
            fails.append(f"{b['name']} unit {u['unit']}: drawn but not in the plot")
        elif real.get("height") != u["height"]:
            fails.append(f"{b['name']} unit {u['unit']}: labelled {u['height']} but "
                         f"hangs at {real.get('height')} — compression reached a NUMBER")
print(f"  ok   {sum(len(b['units']) for b in _lay)} labelled heights are the real heights")

# The endpoint the browser calls and the module the PDF calls are the same call.
_api = client.post("/booms", json={"positions": plot["positions"],
                                   "instruments": plot["instruments"]}).json()
_strip = lambda bs: [(b["name"], round(b["x"], 4), round(b["top"], 4),
                      [round(v, 4) for v in b["breaks"]],
                      [(u["unit"], u["label"], round(u["dy"], 4)) for u in b["units"]])
                     for b in bs]
if _strip(_api["booms"]) != _strip(_lay):
    fails.append("the /booms endpoint and the PDF's own layout disagree")
else:
    print(f"  ok   screen and paper place {len(_lay)} booms identically")

# ---------------------------------------------------------------- labels
# ⭐ A position's NAME has to be readable. Placed at the pipe's stage-left end
# regardless of what was already there, CAT 1 and HOUSE LEFT BOX BOOM 1 landed
# on each other AND on the box boom's symbol — three marks in one place, with
# the one an electrician reads first underneath.
#
# 🔴 And a name must never be fitted somewhere that is not on the paper. The
# first version dodged the box boom by moving CAT 1 to the stage-right end, 22
# feet off the edge of the sheet: a collision traded for a position with no name
# at all, which is the worse of the two.
from plotedit import labels as _L

print()
_meas = lambda t: len(t) * 0.26

# 🔴 THE RULE ITSELF, on cases built to make it fail. Checking only that the
# test plot comes out clean proved nothing: breaking the fitter on purpose
# still passed, because that plot has slack everywhere. These do not.
_first = [(0.0, 10.0, "left"), (0.0, 4.0, "left")]      # preferred, then fallback
_blocked = _L.place([{"candidates": _first, "w": 3.0, "h": 0.4}],
                    obstacles=[_L.disc(1.0, 10.0, 1.2)])[0]
if (_blocked["x"], _blocked["y"]) != (0.0, 4.0):
    fails.append(f"a label sat on an obstacle rather than taking its second "
                 f"choice: {_blocked}")
else:
    print("  ok   a blocked first choice gives way to the next slot")

_clear = _L.place([{"candidates": _first, "w": 3.0, "h": 0.4}], obstacles=[])[0]
if (_clear["x"], _clear["y"]) != (0.0, 10.0):
    fails.append("a label moved although its first choice was clear")
else:
    print("  ok   a clear first choice is kept")

# Off the sheet beats nothing. The clear slot is out of bounds, the crowded one
# is on the paper: take the paper. A name nobody can see is not a name.
_edge = _L.place([{"candidates": [(50.0, 10.0, "left"), (0.0, 10.0, "left")],
                   "w": 3.0, "h": 0.4}],
                 obstacles=[_L.disc(1.0, 10.0, 1.2)],
                 bounds=(-5.0, -5.0, 20.0, 20.0))[0]
if _edge["x"] != 0.0:
    fails.append(f"a label was fitted OFF THE SHEET at x={_edge['x']} to dodge a "
                 f"symbol — a position with no name is worse than a crowded one")
else:
    print("  ok   a slot off the sheet loses to a crowded one that is on it")

# Two labels wanting one spot: the second gives way, the first does not move.
_pair = _L.place([{"candidates": _first, "w": 3.0, "h": 0.4},
                  {"candidates": _first, "w": 3.0, "h": 0.4}])
if _pair[0]["y"] != 10.0 or _pair[1]["y"] != 4.0:
    fails.append(f"two labels took the same slot: {_pair}")
else:
    print("  ok   the second of two labels gives way to the first")

# ---- and the real plot, at the sheet the PDF actually uses
_BOUNDS = (-17.0, -4.0, 23.0, 36.0)
_spots = _L.plan(plot["positions"], plot["instruments"], _meas,
                 room_width=plot["room"]["width"], bounds=_BOUNDS)

if len(_spots) != len(plot["positions"]):
    fails.append(f"{len(plot['positions'])} positions but {len(_spots)} labels")
else:
    print(f"  ok   every one of {len(_spots)} positions keeps its name")

_boxes = [_L._box(s_["x"], s_["y"], _meas(s_["text"]), 0.4, s_["align"]) for s_ in _spots]
for _i in range(len(_boxes)):
    for _j in range(_i + 1, len(_boxes)):
        if _L._overlap(_boxes[_i], _boxes[_j]) > 0:
            fails.append(f"labels collide: {_spots[_i]['text']} over {_spots[_j]['text']}")

_on_sym = [s_ for s_, b in zip(_spots, _boxes)
           if any(_L._overlap(b, _L.disc(i["x"], i["y"], 1.35)) > 0
                  for i in plot["instruments"])]
fails += [f"'{s_['text']}' sits on an instrument" for s_ in _on_sym]
if not _on_sym:
    print("  ok   no name overlaps another name or an instrument")

_lapi = client.post("/labels", json={
    "positions": plot["positions"], "instruments": plot["instruments"],
    "room_width": plot["room"]["width"], "char_w": 0.26, "text_h": 0.4,
    "bounds": list(_BOUNDS)}).json()["labels"]
_key2 = lambda rs: [(r["text"], round(r["x"], 4), round(r["y"], 4), r["align"]) for r in rs]
if _key2(_lapi) != _key2(_spots):
    fails.append("the /labels endpoint and the PDF's own fit disagree — the screen "
                 "and the paper would put the same name in different places")
else:
    print(f"  ok   screen and paper choose the same slot for all {len(_spots)} names")

# The suite's verdict comes LAST, so anything added after it still counts. It
# used to sit in the middle, which meant an appended check could fail while the
# suite exited 0 — the same defect found in test_package.py the same day.
print()
if fails:
    print(f"{len(fails)} DISAGREEMENTS")
    for f in fails:
        print("   ", f)
    sys.exit(1)
print("all agree")
