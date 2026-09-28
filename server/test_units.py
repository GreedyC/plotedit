#!/usr/bin/env python3
"""Feet, metres, and the conversions that must happen exactly once.

    cd server && python3 test_units.py
"""
import sys

from plotedit import units as U
from plotedit.scaled_pdf import SCALES as PDF_SCALES

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("the bridge between the two systems is EXACT")
# ⭐ 1/4" = 1'-0" IS 1:48 — a foot is twelve inches and a quarter inch goes into
# twelve exactly forty-eight times. If this bridge is wrong, every metric
# drawing is wrong by a ratio nobody would think to check, and the drawing still
# looks like a drawing.
for scale, ratio in [("1/8", 96.0), ("1/4", 48.0), ("3/8", 32.0),
                     ("1/2", 24.0), ("3/4", 16.0), ("1", 12.0)]:
    check(f'{scale}" = 1\'-0" is 1:{ratio:g}', U.scale_ratio(scale), ratio)
check("and a metric ratio is itself", U.scale_ratio("1:50"), 50.0)

print("\n...so the new scale model is DROP-IN for every existing scale")
# 🔴 scaled_pdf computes pt_per_ft as paper_in_per_ft * 72 and its own comment
# calls that "the whole trick". If points_per_foot() disagrees by so much as a
# rounding error, every drawing already made changes size.
for name, inches_per_foot in PDF_SCALES.items():
    check(f"pt/ft at {name}\" unchanged",
          round(U.points_per_foot(name), 9), round(inches_per_foot * 72, 9))

print("\na length survives the round trip")
# 🔴 THE DANGER IS DOUBLE CONVERSION, and it is silent — a length converted
# twice is out by 10.76 and still describes a plausible room.
for system in U.SYSTEMS:
    for ft in (0.0, 1.0, 13.3333, 38.0, -4.5):
        back = U.to_feet(U.feet_to(ft, system), system)
        check(f"{system}: {ft} ft -> display -> {ft} ft", round(back, 9), round(ft, 9))

# The specific failure that guard is for, stated so it cannot creep back.
_twice = U.feet_to(U.feet_to(10.0, U.METRIC), U.METRIC)
check("converting twice is NOT the identity (it is the bug)",
      round(_twice, 4) == round(U.feet_to(10.0, U.METRIC), 4), False)

print("\nhow each system writes a length")
check("imperial rounds to the inch", U.fmt_length(13.3333), "13'-4\"")
check("...and carries a sign", U.fmt_length(-2.5), "-2'-6\"")
check("...exactly on the foot", U.fmt_length(14.0), "14'-0\"")
check("metric rounds to the centimetre", U.fmt_length(13.3333, U.METRIC), "4.06 m")
check("nothing is an em dash, not a zero", U.fmt_length(None), "—")

print("\nand what it calls the light")
# 🔴 THE LABEL IS THE POINT. "179 fc" printed over a lux number is a false
# statement that looks authoritative.
check("footcandles imperial", U.fmt_illuminance(773), "773 fc")
check("lux metric", U.fmt_illuminance(773, U.METRIC), "8321 lx")
check("1 fc is 10.7639 lx", round(U.LUX_PER_FC, 4), 10.7639)
check("unknown says so", U.fmt_illuminance(None, U.METRIC), "—")

print("\ndefaults are IDIOMATIC, not converted")
# 🔴 Head height is 5'-6" imperial; a metric designer says 1.7 m, not 1.676 m.
# Converted defaults produce numbers no European would type, and they then
# travel into drawings as evidence of a measurement nobody took.
_metric = {k: v for k, _, v in U.POOL_PLANES[U.METRIC]}
check("metric head height reads exactly 1.70 m",
      U.fmt_length(_metric[""], U.METRIC), "1.70 m")
check("...and is NOT a conversion of 5'-6\"",
      U.fmt_length(5.5, U.METRIC) == "1.70 m", False)

# ⚠ EVERY metric default, not just the first. Checking head height alone let a
# converted `face` default through when I broke it on purpose: 5'-2" is 1.5748 m,
# which displays as "1.57 m" — a number no designer would ever type, and the
# tell that it was converted rather than chosen. An idiomatic metric height
# lands on a round decimetre.
_odd = [(k, U.fmt_length(v, U.METRIC))
        for k, _, v in U.POOL_PLANES[U.METRIC]
        if not U.fmt_length(v, U.METRIC).endswith("0 m")]
check("every metric default is a round decimetre", _odd, [])
check("the deck is the deck in both", _metric["deck"], 0.0)
check("both systems offer the same planes",
      [k for k, _, _ in U.POOL_PLANES[U.IMPERIAL]],
      [k for k, _, _ in U.POOL_PLANES[U.METRIC]])

print("\nan existing plot keeps reading the way it was drawn")
check("no units field means imperial", U.system_of({"show": "x"}), U.IMPERIAL)
check("an empty plot too", U.system_of(None), U.IMPERIAL)
check("metric when it says so", U.system_of({"units": "metric"}), U.METRIC)

print()
print("a metric plot DRAWS metric")
import json as _json, os as _os, re as _re, tempfile as _tf
import fitz as _fitz
from plot_to_pdf import render as _render

_SAMPLE = _os.path.join(_os.path.dirname(__file__), "testdata", "blackbox.plot.json")
_src = _json.load(open(_SAMPLE))
_FEET = _re.compile(r"-?\d+'-\d+\"|-?\d+'(?!\w)")
_METRES = _re.compile(r"-?\d+\.\d+\s?m\b")


def _drawn(scale="fit", **over):
    """⚠ "fit" is the NORMAL path and the only one that tests anything here.
    Forcing scale="1/4" on a metric plot is a deliberate override, and it
    correctly prints an imperial label — asserting against that would be
    asserting the override works, not that metric does."""
    body = dict(_src); body.update(over); body["rulers"] = True
    d = _tf.mkdtemp()
    jp = _os.path.join(d, "p.json"); _json.dump(body, open(jp, "w"))
    out = _os.path.join(d, "p.pdf")
    sheet, _ = _render(jp, out, scale=scale)
    return sheet, _fitz.open(out)[0].get_text()


_imp_sheet, _imp = _drawn()
_met_sheet, _met = _drawn(units="metric")

check("an imperial plot is full of feet", len(_FEET.findall(_imp)) > 30, True)
check("...and carries no metre lengths", _METRES.findall(_imp), [])
check("a metric plot carries metre lengths", len(_METRES.findall(_met)) > 0, True)

# ⭐ AND NOW THERE ARE NONE. This assertion used to list the four feet that
# survived — the scale bar and the scale label — because the drawing SCALE was
# still imperial. Finishing that work had to come back and change this line,
# which is exactly what it was written to force.
check("NOTHING on a metric sheet is written in feet",
      sorted(set(_FEET.findall(_met))), [])

check("the room DIMENSION converts", "10.06 m" in _met or "11.58 m" in _met, True)
check("the sheet knows its own system",
      (_imp_sheet.unit_system, _met_sheet.unit_system), ("imperial", "metric"))

print()
print("illuminance is labelled to match, or it is a false statement")
check("imperial says fc", _imp_sheet.fmt_lux(179.0), "179 fc")
check("metric says lx", _met_sheet.fmt_lux(179.0), "1927 lx")
check("and it is a real conversion, not a relabel",
      _met_sheet.fmt_lux(179.0) != "179 lx", True)

print()
print("the endpoint formats in the system it is asked for")
from fastapi.testclient import TestClient as _TC
from plotedit.api import app as _app
_client = _TC(_app)
_inst = [{"unit": 1, "channel": 1, "type": "S4 26", "x": 0, "y": 20, "trim": 14,
          "focus_x": 0, "focus_y": 8, "focus_h": 5.5}]
_a = _client.post("/compute", json={"instruments": _inst}).json()["instruments"][0]
_b = _client.post("/compute", json={"instruments": _inst, "units": "metric"}).json()["instruments"][0]
check("asking for nothing gets feet", _a["throw_ft"].endswith('"'), True)
check("asking for metric gets metres", _b["throw_ft"].endswith(" m"), True)
check("the underlying number is the SAME — only the label moved",
      _a["throw"], _b["throw"])

print()
print("a metric plot is DRAWN at a metric ratio")
from plotedit.scaled_pdf import Sheet as _Sheet, fit_scales as _fit, FIT_SCALES_METRIC
import tempfile as _tf2, os as _os2

check("1/4 inch is 1:48 exactly", U.scale_ratio("1/4"), 48.0)
check("...so a quarter-inch sheet and a 1:48 sheet are the same drawing",
      round(U.points_per_foot("1/4"), 6), round(U.points_per_foot("1:48"), 6))

def _sheet(sc):
    return _Sheet(_os2.path.join(_tf2.mkdtemp(), "s.pdf"), scale=sc)

_q, _fifty = _sheet("1/4"), _sheet("1:50")
check("an imperial sheet says so", _q.scale_label, "1/4\" = 1'-0\"")
check("a metric sheet says its ratio", _fifty.scale_label, "1:50")
check("...and is very slightly smaller than a quarter inch",
      _fifty.pt_per_ft < _q.pt_per_ft, True)

check("the fit ladder follows the system",
      (_fit(U.IMPERIAL)[0], _fit(U.METRIC)[0]), ("1", "1:10"))
check("...and metric climbs real drafting ratios",
      _fit(U.METRIC), FIT_SCALES_METRIC)

_ms, _mt = _drawn(units="metric")
check("the fitted metric scale is a ratio", _ms.scale_label.startswith("1:"), True)
# ⚠ Asserted against the PLAN, not against a hardcoded "5 m". The bar is sized
# to the paper now, so how many divisions it has depends on the scale — a test
# naming a specific number breaks whenever that sizing is tuned, and tells you
# nothing about whether the unit is right.
_divs, _step, _total, _per = _ms.scale_bar_plan()
_end = f"{_divs * _per:g} m"
check("the scale bar's last mark is in metres", _end in _mt, True)
# ⚠ And the geometry, not just the label. A bar reading "0 5 10 m" with
# one-foot divisions is 3.28 times too short and is the one thing on the sheet
# somebody would physically measure against.
check("...and one division really IS a metre",
      round(_ms.scale_bar_step(), 6), round(_ms.pt_per_ft * U.FOOT_PER_M, 6))
check("...while an imperial division is a foot",
      round(_imp_sheet.scale_bar_step(), 6), round(_imp_sheet.pt_per_ft, 6))
# A print check, not a drawing scale: it proves the sheet came out at 100%.
check("the print check is 50 mm on a metric sheet",
      "50 mm when printed at 100%" in _mt, True)
check("...and an inch on an imperial one",
      'bar is 1" when printed at 100%' in _imp, True)

# ⚠ And the override still behaves: a metric plot FORCED to a quarter inch says
# so on its face rather than claiming a ratio it was not drawn at.
_forced_sheet, _forced = _drawn(scale="1/4", units="metric")
check("a metric plot forced to an imperial scale admits it",
      _forced_sheet.scale_label, "1/4\" = 1'-0\"")
check("...while its lengths stay metric", "10.06 m" in _forced, True)

print()
print("everything the SERVER formats for the screen follows the plot too")
# 🔴 Jerry, 2026.09.26: "the dimensions on the boom are imperial, at least on
# the screen." They were. Boom height labels are built on the server — the
# browser is deliberately not allowed to retype that arithmetic — and the
# formatter was never told which system, so a metric plot drew its boom
# elevation in feet on screen while the PDF beside it said metres.
#
# ⚠ Same shape as the lux bug an hour earlier: a formatter that takes a system,
# a caller that does not pass one. Worth testing every server-formatted string
# rather than the one that was reported.
from plotedit import booms as _booms, labels as _labels

_bi = _booms.layout(_src["positions"], _src["instruments"], system=U.IMPERIAL)
_bm = _booms.layout(_src["positions"], _src["instruments"], system=U.METRIC)
_li = [u["label"] for b in _bi for u in b["units"]]
_lm = [u["label"] for b in _bm for u in b["units"]]
check("there are boom units to label at all", len(_li) > 0, True)
check("imperial boom heights are feet and inches",
      all(l.endswith('"') for l in _li), True)
check("metric boom heights are metres", all(l.endswith(" m") for l in _lm), True)
check("...and it is the same height, written differently", len(_li), len(_lm))

_trim = {"name": "E1", "type": "electric", "x1": 0, "y1": 20, "x2": 33, "y2": 20,
         "trim": 14.0, "movable": True}   # trim shows only on a movable position
check("a position label's trim is imperial by default",
      _labels.text_for(_trim).endswith("14'-0\""), True)
# ⚠ Lowercase m. Position names are drawn in CAPS and the unit symbol went with
# them, so a metric trim read "4.27 M" — which in SI is a mega- prefix, not
# metres. Feet and inches survive uppercasing; metres do not.
check("...and metric when the plot is, with a lowercase metre",
      _labels.text_for(_trim, U.METRIC), "E1 — TRIM 4.27 m")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
