#!/usr/bin/env python3
"""Smoke test: every module imports as a package and the chains hold.

    cd server && python3 test_package.py

Not a unit-test suite. It answers one question — is the package wired up —
and it checks the values that have been wrong before.
"""
import os
import sys

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<44} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("imports")
from plotedit import photometrics as ph
from plotedit import dxf_bridge, eos_ascii, paperwork
from plotedit.scaled_pdf import Sheet, ft, check as pdf_check
print("  ok   all six modules")

print("\nphotometrics — figures from ETC datasheets")
check("S4 26 field angle", ph.FIXTURES["S4 26"]["field"], 25.0)
check("gels.csv found beside the module", len(ph.GELS), 11)
check("R119 transmission", ph.GELS["R119"]["t"], 0.893)

print("\ngel notation — + stacks, / splits")
check("R52+R119 stacked", round(ph.gel_factor("R52+R119")[0], 3), 0.232)
check("R52/R119 split -> first gel only", round(ph.gel_factor("R52/R119")[0], 3), 0.26)
check("unknown gel -> no guess", ph.gel_factor("L201")[0], None)

print("\nscaled_pdf -> photometrics -> gels")
s = Sheet(os.devnull, page="TABLOID", scale="1/4")
s.origin(ft(3), ft(5))
r = s.unit(ft(6), ft(20), 1, ch=1, kind="S4 26", color_gel="R52+R119",
           trim=14, focus_to=(ft(10), ft(10)), lamp="HPL 575")
# Regression: a compound gel used to miss a dict lookup and silently report
# open white — 729 fc instead of 169. The acting-area wash, 4.5x too bright.
check("R52+R119 acting-area wash", round(r["fc"]), 169)
check("throw", ph.fmt_ft(r["throw"]), "13'-9\"")

print("\nscaled_pdf -> dxf_bridge, and the printed scale")
out = os.path.join(os.path.dirname(__file__), "..", "out")
os.makedirs(out, exist_ok=True)
pdf, dxf = os.path.join(out, "smoke.pdf"), os.path.join(out, "smoke.dxf")
s = Sheet(pdf, page="TABLOID", scale="1/4", landscape=False, show="smoke test", dxf=dxf)
s.origin(ft(3), ft(5))
s.rect(0, 0, ft(33), ft(38), width=1.5)     # the Bluver, which needs portrait at 1/4"
s.finish()
check("DXF written alongside", os.path.exists(dxf), True)
check("1-inch check bar", round(pdf_check(pdf), 2), 72.0)
check("portrait fits, no warning", s.warnings, [])

# The same room landscape does NOT fit. The tool must say so rather than clip
# silently — a drawing that runs off the sheet looks finished and is not.
s2 = Sheet(os.devnull, page="TABLOID", scale="1/4", landscape=True)
s2.origin(ft(3), ft(3))
s2.rect(0, 0, ft(33), ft(38))
s2.finish()
check("landscape clips, and says so", len(s2.warnings), 1)
check("names a scale that would fit", '1/8"' in (s2.warnings[0] if s2.warnings else ""), True)

print("\neos_ascii")
asc = eos_ascii.build("Test", {"Study": [1, 2]},
                      [(1, "Q1 up", 5, 5, {"Study": 85})])
check("85% written as hex Hd9", "1@Hd9" in asc, True)
check("TimeUp written (or long fades collapse)", "$$TimeUp 5 0 0 0" in asc, True)

print("\nsymbols — USITT RP-2 (2006)")
from plotedit import symbols as sym
# "S4 26" must not parse as 4 degrees — it did, once.
check("S4 26 gets the 26-30 diagonal, one line",
      sum(1 for p in sym.for_type("S4 26") if p[0] == "line"), 1)
check("S4 19 gets the X, two lines",
      sum(1 for p in sym.for_type("S4 19") if p[0] == "line"), 2)
check("S4 36 carries no mark",
      sum(1 for p in sym.for_type("S4 36") if p[0] == "line"), 0)
check("Lustr = 7 dots, per 6.16",
      sum(1 for p in sym.for_type("Lustr 26 EDLT") if p[0] == "circle"), 7)
check("a mover gets a dashed swing circle",
      any(p[0] == "circle" and len(p) > 3 and p[3] == "dashed"
          for p in sym.for_type("Martin Mac Aura")), True)
# The flare is the whole point: RP-2's lens housing opens out to a face WIDER
# than the body. The first attempt had it narrowing, which read as a funnel.
_pts = sym.enhanced_ers(26)[0][1]
_face_w = _pts[0][1]                       # first point is the front face
_body_w = max(c for _, c in _pts)
check("the front face is the widest point", round(_face_w, 4), round(_body_w, 4))

print("\nline weights — RP-2 6.18, three and only three")
from plotedit.scaled_pdf import LINE_STYLES, LIGHT, MEDIUM, HEAVY
check("exactly three weights are used",
      sorted({w for w, _ in LINE_STYLES.values()}), [LIGHT, MEDIUM, HEAVY])
check("a batten is heavy", LINE_STYLES["batten"][0], HEAVY)
check("a luminaire is heavy", LINE_STYLES["luminaire"][0], HEAVY)
check("architecture is heavy", LINE_STYLES["architecture"][0], HEAVY)
check("scenery is light", LINE_STYLES["scenery"][0], LIGHT)
check("a dimension is light", LINE_STYLES["dimension"][0], LIGHT)
check("the center line is a 4-part chain dash", len(LINE_STYLES["centerline"][1]), 4)
check("the plaster line is evenly dashed", len(LINE_STYLES["plasterline"][1]), 2)
try:
    from plotedit.scaled_pdf import style as _style
    _style("chunky")
    check("an unknown category is refused", "no error", "KeyError")
except KeyError:
    check("an unknown category is refused", "KeyError", "KeyError")

print("\npaperwork")
check("Lightwright column aliases", len(paperwork.LW_COLUMNS), 37)


# ---------------------------------------------------------------- accessories
print("\naccessories attach where RP-2 puts them, not where they were typed")
from plotedit import symbols as _sym

check("a hat is front-of-lens",  _sym.resolve_accessory("top hat")[0], "front")
check("a gobo is at the gate",   _sym.resolve_accessory("gobo")[0], "gate")
check("'4-way barn door' reads", _sym.resolve_accessory("4-way barn door")[1], "bd4")
check("a bare 'barn door' is the 4", _sym.resolve_accessory("barn door")[1], "bd4")
# An accessory this tool cannot draw must SAY so. A barn door that is silently
# dropped is a barn door nobody packs.
where, key, note = _sym.resolve_accessory("scroller")
check("an unknown accessory resolves to nothing", where, None)
check("...and explains itself", "not an accessory this tool knows" in note, True)

_base = _sym.for_type("S4 26")
_with, _unknown = _sym.with_accessories(_base, ["top hat", "gobo"])
check("two accessories add geometry", len(_with) > len(_base), True)
check("...and neither is unknown", _unknown, [])
_, _unknown2 = _sym.with_accessories(_base, ["scroller"])
check("an unknown one is REPORTED, not dropped", len(_unknown2), 1)

# The front accessory must sit at the nose, in front of the body — not on top
# of it. Its geometry should extend further forward than the symbol does.
_fa_base, _ = _sym._extent(_base), None
_fa_with = _sym._extent(_with)
check("the hat sits forward of the body", _fa_with[0] < _sym._extent(_base)[0], True)

# Two hats must not land on each other.
_two, _ = _sym.with_accessories(_base, ["top hat", "half hat"])
check("a second front accessory stacks further out",
      _sym._extent(_two)[0] < _sym._extent(_with)[0], True)



# ------------------------------------------------------------------ positions
print("\npositions: a catwalk is not a pipe, and it is front of house")
from plotedit.scaled_pdf import Sheet as _Sheet

_cat = {"name": "Cat 1", "type": "catwalk", "x1": 0, "y1": -11, "x2": 33,
        "y2": -11, "width": 3.0}
_elec = {"name": "Elect 1", "type": "electric", "x1": 0, "y1": 16, "x2": 33, "y2": 16}

# ⭐ CORRECTED 2026.09.24. These asserted that a catwalk sat OUTSIDE the room at
# negative y and that the sheet had to be extended downstage to reach it. Jerry:
# "the FOH catwalk would need to be inside the room." He is right — the room is
# the whole room, house and stage, divided by the plaster line. Nothing sits
# beyond it, so foh_extent() is retired and returns 0.
check("nothing needs the sheet extended any more", _Sheet.foh_extent([_cat, _elec]), 0.0)

# FOH is now a matter of WHERE a position sits, not the sign of its y.
# Imported here rather than relying on where else in this file it happens to be
# bound — the second time today that bit me, and the note I wrote about it last
# time was three hundred lines away where I could not see it.
import json as _json
from plotedit import positions as P
_room = {"room": {"width": 33, "depth": 38, "plasterLine": 10.0}}
check("in a proscenium house, downstage of the plaster line is FOH",
      P.is_foh({"name": "Cat 1", "y1": 4.0}, 10.0), True)
check("upstage of it is not", P.is_foh({"name": "E1", "y1": 16.0}, 10.0), False)
check("an explicit flag still wins",
      P.is_foh({"name": "X", "y1": 16.0, "foh": True}, 10.0), True)

# ⭐ A BLACK BOX HAS NO PLASTER LINE — no proscenium, so nothing for "downstage
# of" to mean. What divides house from stage is the SEATING, and at the Bluver
# the risers move per production. So the flag is the designer's statement, not
# something geometry can work out.
check("with no plaster line, geometry cannot decide", P.is_foh({"name": "X", "y1": 4.0}), False)
check("...so the flag is the only answer",
      P.is_foh({"name": "X", "y1": 4.0, "foh": True}), True)

# RP-2 §3 already allows for it: "proscenium, plaster line, smoke pocket, OR the
# horizontal zero location". A plaster line is one KIND of zero, not the only one.
check("a proscenium house names its plaster line",
      P.horizontal_zero({"plasterLine": 10})["name"], "plaster line")
check("a black box names something else",
      P.horizontal_zero({"horizontalZero": {"y": 0, "name": "downstage wall"}})["name"],
      "downstage wall")
check("and a room that declares nothing gets nothing invented",
      P.horizontal_zero({}), None)

# ⚠ The flag and the geometry are two statements of one fact, so they can
# contradict each other silently. Found in this tool's OWN sample: a boom
# flagged foh=false at y=9 with the plaster line at y=10.
# Only checkable where there IS a plaster line to contradict.
check("a contradicted flag is caught in a proscenium house",
      any("One of the two is wrong" in m for m in P.check_foh(
          {**_room, "positions": [{"name": "B", "y1": 9.0, "foh": False}]})), True)
check("...and not invented in a black box",
      P.check_foh({"room": {"width": 33, "depth": 38,
                            "horizontalZero": {"y": 0, "name": "downstage wall"}},
                   "positions": [{"name": "B", "y1": 9.0, "foh": False}]}), [])
check("a position outside the room is caught",
      any("OUTSIDE the room" in m for m in P.check_foh(
          {**_room, "positions": [{"name": "C", "y1": -11.0}]})), True)
check("the sample itself is now consistent",
      P.check_foh(_json.load(open("../samples/bluver.plot.json"))), [])

# The catwalk is still a WALKWAY — three distinct lines, pipe inboard.
_half = _cat["width"] / 2
_lines = {_cat["y1"] + _half, _cat["y1"] - _half, _cat["y1"] - _half * 0.55}
check("a catwalk draws three distinct lines", len(_lines), 3)
check("the pipe sits inboard of the downstage edge",
      _cat["y1"] - _half * 0.55 > _cat["y1"] - _half, True)



print("\nRP-2 §2.3.2 numbering: stage left across a batten, top down on a boom")
from plotedit import positions as P

# ⭐ RP-2 §2.3.2: battens number "from STAGE LEFT TO STAGE RIGHT"; vertical
# positions "from top to bottom, downstage to upstage".
#
# ⚠ x increases toward stage right and y increases upstage (geometry.ts, and the
# sample puts "Special SR" at x=22 against "Special SL" at x=11 in a 33' room).
# So stage left is the MINIMUM x and downstage the MINIMUM y.
_lat = {"name": "Elect 1", "x1": 0, "y1": 16, "x2": 33, "y2": 16}
_lon = {"name": "Pipe SR", "x1": 28, "y1": 2, "x2": 28, "y2": 26}
check("a wide position is lateral", P.axis(_lat), "lateral")
check("a deep one is longitudinal", P.axis(_lon), "longitudinal")
check("lateral units number from stage left (RP-2 §2.3.2)",
      P.number_from(_lat), "SL")
check("longitudinal defaults to downstage", P.number_from(_lon), "DS")

_i = [dict(unit=99, position="Elect 1", x=x, y=16) for x in (5, 12, 22, 30)]
P.number(_i, _lat)
check("unit 1 is the LOWEST x — stage left", next(i["x"] for i in _i if i["unit"] == 1), 5)
check("...and unit 4 the highest", next(i["x"] for i in _i if i["unit"] == 4), 30)

_j = [dict(unit=99, position="Pipe SR", x=28, y=y) for y in (4, 10, 18, 24)]
P.number(_j, _lon)
check("unit 1 is the LOWEST y — farthest downstage",
      next(i["y"] for i in _j if i["unit"] == 1), 4)

# The override Jerry asked for.
check("an explicit numberFrom wins", P.number_from(dict(_lat, numberFrom="SR")), "SR")
_k = [dict(unit=99, position="Elect 1", x=x, y=16) for x in (5, 30)]
P.number(_k, dict(_lat, numberFrom="SR"))
check("...and reverses the order", next(i["x"] for i in _k if i["unit"] == 1), 30)

# Two units at one coordinate cannot be ordered. Picking one is how a plot gets
# hung backwards, so it must warn rather than choose.
_dup = [dict(unit=99, position="Elect 1", x=12, y=16) for _ in range(2)]
_, _w = P.number(_dup, _lat)
check("units sharing a coordinate warn", "arbitrary" in (_w or ""), True)
check("an empty position warns too", P.number([], _lat)[1] is not None, True)


print("\ncircuits: recorded from the house, never invented")
from plotedit import circuits as C

# "Circuits depend on the house — no set order." (Jerry, 2026.09.23.) So the
# tool records and checks; it never generates a circuit number.
_p1 = {"name": "Elect 1", "x1": 0, "y1": 16, "x2": 33, "y2": 16,
       "circuits": [{"id": 3, "x": 4}, {"id": 4, "x": 28}],
       "circuitSource": "Drake rep plot 2019"}
_p2 = {"name": "Elect 2", "x1": 0, "y1": 20, "x2": 33, "y2": 20,
       "circuits": [7, 8], "circuitSource": "ME, by phone"}
_p3 = {"name": "Elect 3", "x1": 0, "y1": 24, "x2": 33, "y2": 24}

check("a bare list still reads", C.available(_p2), [7, 8])
check("locations survive", C.available(_p1), [3, 4])
check("an unsourced list says so", "NOT RECORDED" in C.source(_p3), True)

# A circuit the house does not list is a real error, not a warning.
_bad = [{"unit": 1, "position": "Elect 1", "circuit": 99, "x": 4, "y": 16}]
check("a circuit the house has not got is caught",
      any("does not list" in m for m in C.check(_bad, [_p1])), True)

# A twofer is legal and is a LOAD question, so it is reported, not rejected.
_two = [{"unit": 1, "position": "Elect 1", "circuit": 3, "x": 4, "y": 16},
        {"unit": 2, "position": "Elect 1", "circuit": 3, "x": 6, "y": 16}]
check("a twofer is reported as a load question",
      any("twofer" in m for m in C.check(_two, [_p1])), True)
check("a position with no circuits is noted, not failed",
      any("no circuits recorded" in m for m in C.check([], [_p3])), True)

# ⭐ The refusal. Without locations there is no basis for matching, and pairing
# a list against units in order would look like a result and be a guess.
_n, _notes = C.match_to_units(_two, _p2)
check("matching REFUSES when the house gave no locations", _n, 0)
check("...and says why", any("no set order" in m for m in _notes), True)

# With locations it matches — and must report every doubling it creates.
_many = [{"unit": u, "position": "Elect 1", "x": x, "y": 16}
         for u, x in [(1, 3), (2, 5), (3, 27)]]
_n, _notes = C.match_to_units(_many, _p1)
check("with locations it matches", _n, 3)
check("more units than circuits is flagged",
      any("MUST double up" in m for m in _notes), True)
check("...and the twofer it made is named",
      any("twofer" in m for m in _notes), True)


print("\ndimmer-per-circuit: the circuit and the dimmer are ONE number")
# Jerry, 2026.09.23: "most houses have circuit per dimmer." RP-2 6.14.1 notates
# the three control models differently, and in this one a second container tells
# the electrician there is a patch to make when there is not.
check("the three models are named", len(sym.CONTROL_MODELS), 3)
_pp = [{"name": "E1", "x1": 0, "y1": 16, "x2": 33, "y2": 16,
        "circuits": [3, 4], "circuitSource": "rep plot"}]
_ii = [{"unit": 1, "position": "E1", "circuit": 3, "dimmer": 3},
       {"unit": 2, "position": "E1", "circuit": 4, "dimmer": 112}]
check("circuit != dimmer is caught in a dimmer-per-circuit house",
      any("one number" in m for m in C.check(_ii, _pp)), True)
check("...and is fine in a patch house",
      any("one number" in m for m in C.check(_ii, _pp, control="hard-and-soft-patch")),
      False)

print("\nload: a tungsten unit's watts belong to its LAMP")
# The same Source Four is 575W or 750W depending on what is in it, so a wattage
# stored against the fixture would be wrong for half the rig.
check("HPL 575 is 575 watts", ph.lamp_watts("HPL 575"), 575.0)
check("HPL 750 is 750", ph.lamp_watts("HPL 750"), 750.0)
check("the long-life 575X is still 575", ph.lamp_watts("HPL 575X"), 575.0)
# ⭐ The one that matters. A loose number-search finds 3200 in "Regulated 3200K"
# and calls it 3200 watts — a number that looks real, lands in a load total and
# trips a breaker. An LED MODE IS NOT A LAMP.
check("an LED mode is NOT a lamp", ph.lamp_watts("Regulated 3200K"), None)
check("nor is a bare colour temperature", ph.lamp_watts("5600K"), None)
check("nor is a mode with no number", ph.lamp_watts("Boost"), None)

_load = [{"unit": u, "position": "E1", "circuit": 3, "type": "S4 26", "lamp": "HPL 575"}
         for u in (1, 2, 3, 4)]
_rows, _notes = C.load(_load, _pp, dimmer_watts=2400)
check("four 575s is 2300W", _rows[0]["watts"], 2300.0)
check("...which is inside 2400", _rows[0]["headroom_pct"] > 0, True)
_rows, _notes = C.load(_load + [dict(_load[0], unit=5, lamp="HPL 750")], _pp,
                       dimmer_watts=2400)
check("a fifth unit puts it over", any("is OVER" in m for m in _notes), True)

# ⚠ Without a rating nothing is judged. A capacity check against a number nobody
# confirmed reads as a pass, which is worse than no check at all.
check("no rating means no verdict",
      any("nothing is judged" in m for m in C.load(_load, _pp)[1]), True)
# The Spectra Cyc 50 is the example now: Altman publish no wattage for it at all.
# (It was the SHEHDS until 2026.09.23, when its 350W turned out to be recorded in
# Jerry's own rig notes — see below.)
check("units with no wattage are named, and the total called a floor",
      any("a floor, not a total" in m
          for m in C.load([{"unit": 9, "position": "E1", "circuit": 3,
                            "type": "Altman Spectra Cyc 50"}], _pp)[1]), True)


print("\nan S4 with no lamp recorded is an HPL 575, not the reference 750")
# Jerry, 2026.09.23: "ETC S4 incandescents are 575 watts unless noted - there
# are 750." ETC MEASURED the candela at HPL 750, but a 750 is not what is in the
# fixture. Computing an unstated lamp at the reference overstates every level by
# about a quarter, in the direction that looks safe — the plot promises light the
# rig will not deliver.
check("the default lamp is the 575", ph.DEFAULT_LAMP, "HPL 575")
_d = ph.footcandles("S4 26", 14)
check("an unstated lamp computes at 575", round(_d[0]), 700)
check("...and the note says it was assumed", "assumed" in _d[1], True)
check("an explicit 750 still computes at 750",
      round(ph.footcandles("S4 26", 14, lamp="HPL 750")[0]), 898)
check("...without claiming it was assumed",
      "assumed" in ph.footcandles("S4 26", 14, lamp="HPL 750")[1], False)
# ⭐ Corroboration from outside the code: how-we-light.md, built from Jerry's own
# paperwork before any of this existed, puts a 575 S4 26 at 14ft through
# R52+R119 at 163 fc. The default now agrees with his own business file.
check("163 fc through R52+R119 — matches how-we-light.md",
      round(ph.footcandles("S4 26", 14, gel="R52+R119")[0]), 163)

print("\nwattage: the engine's, not the lens tube's — and it varies by mode")
check("an unstated S4 is 575W", ph.watts_for("S4 26")[0], 575.0)
check("a stated 750 is 750W", ph.watts_for("S4 26", lamp="HPL 750")[0], 750.0)
check("a Lustr is ETC's 167", ph.watts_for("Lustr 26 EDLT")[0], 167.0)
check("a ColorSource CYC is 133", ph.watts_for("ColorSource CYC")[0], 133.0)
# ⚠ The one a single number per fixture would get wrong: a ColorSource draws 160W
# at Maximum Output and 115W regulated to 3200K. 28% — the difference between
# four and five units on a 20-amp dimmer.
check("ColorSource at Maximum Output is 160",
      ph.watts_for("ColorSource Spot 26 EDLT", mode="Maximum Output")[0], 160.0)
check("...and 115 regulated to 3200K",
      ph.watts_for("ColorSource Spot 26 EDLT", mode="Regulated 3200K")[0], 115.0)
check("every wattage names its source",
      "datasheet" in ph.watts_for("Lustr 26 EDLT")[1].lower()
      or "Guide" in ph.watts_for("Lustr 26 EDLT")[1], True)
# A fixture with no published figure is reported, not estimated.
_w, _n = ph.watts_for("Altman Spectra Cyc 50")
check("an unpublished wattage stays None", _w, None)
check("...and says to get the datasheet", "datasheet" in _n, True)

# ⭐ A row's OWN wattage beats the family default. The Spectra Cyc 100 carries
# 94.1W straight off its IES file — a real measurement — and watts_for() used to
# look only at FAMILY_WATTS, so a cyc counted as ZERO in a load table while the
# number sat in the row two feet away.
check("a row's own wattage is used", ph.watts_for("Altman Spectra Cyc 100 RGBA")[0], 94.1)
check("...and cites the IES it came from",
      "IES" in ph.watts_for("Altman Spectra Cyc 100 RGBA")[1], True)

# Jerry's own units: "forget the SHEHDS units, that was a one off" (2026.09.23).
# The OUTPUT is closed — unpublished, not being sought, not a task. The WATTAGE
# was in his own rig notes all along and is the part that mattered, because a
# 350W unit counting as zero understates a load in the direction that trips.
check("a SHEHDS is 350W, from the model and Jerry's own notes",
      ph.watts_for("SHEHDS 19")[0], 350.0)
check("...and its candela is still, deliberately, unknown",
      ph.FIXTURES["SHEHDS 19"]["cd"], None)
check("...with the source saying it is not being chased",
      "one-off" in ph.FIXTURES["SHEHDS 19"]["source"], True)


print("\nbooms: a pipe that stands up is a POINT in plan")
_boom = {"name": "HR Boom 1", "type": "boom", "x1": 30, "y1": 9, "x2": 30,
         "y2": 9, "mount": "boom-base"}
_box = {"name": "HL Box Boom 1", "type": "box-boom", "x1": 2, "y1": -9,
        "x2": 2, "y2": -9, "mount": "flange"}
check("a boom is vertical", P.is_vertical(_boom), True)
check("so is a box boom", P.is_vertical(_box), True)
check("an electric is not", P.is_vertical({"type": "electric", "x1": 0, "y1": 16,
                                           "x2": 33, "y2": 16}), False)
# An untyped position with no length is a point, so it stands up.
check("a zero-length position is read as vertical",
      P.is_vertical({"x1": 5, "y1": 5, "x2": 5, "y2": 5}), True)

# ⭐ On a boom the HEIGHT is the only thing separating one unit from another —
# they share an x and a y. RP-2's own 6.12 plate numbers top down: 1 at 8'-0",
# 4 at 2'-0".
check("a boom numbers from the top", P.number_from(_boom), "TOP")
_bu = [{"unit": 9, "position": "HR Boom 1", "height": h, "x": 30, "y": 9}
       for h in (4.5, 12, 8)]
P.number(_bu, _boom)
check("unit 1 is the HIGHEST",
      next(i["height"] for i in _bu if i["unit"] == 1), 12)
check("...and unit 3 the lowest",
      next(i["height"] for i in _bu if i["unit"] == 3), 4.5)

# RP-2 6.12: "Choose only one type of layout per plot."
_mixed = {"positions": [dict(_boom, layout="option1"), dict(_box, layout="option2")],
          "instruments": [{"unit": 1, "position": "HR Boom 1", "height": 8}]}
check("two boom layouts on one plot is caught",
      any("only one type of layout" in m for m in P.check_booms(_mixed)), True)

# A unit with no height cannot be drawn, numbered or hung.
_noh = {"positions": [_boom],
        "instruments": [{"unit": 1, "position": "HR Boom 1", "height": 8},
                        {"unit": 2, "position": "HR Boom 1"}]}
check("a boom unit with no height is caught",
      any("no height" in m for m in P.check_booms(_noh)), True)
check("a missing mount is caught",
      any("no mount recorded" in m
          for m in P.check_booms({"positions": [dict(_boom, mount=None)],
                                  "instruments": []})), True)
check("no booms, no complaints", P.check_booms({"positions": [], "instruments": []}), [])

# The three mounts are different hardware, not three ways of drawing one thing.
check("floor plate, boom base and flange all draw",
      len({len(sym.boom_mount(m)) for m in ("floor-plate", "boom-base", "flange")}), 3)
check("hatching produces lines", len(sym.hatch(sym.for_type("S4 26"))) > 5, True)


print("\nladders hang, tormentors are bolted on, and RP-2 §2.3.2 gives the tiebreak")
_lad = {"name": "SL Ladder 1", "type": "ladder", "x1": 4, "y1": 14, "x2": 4,
        "y2": 14, "trim": 16}
_torm = {"name": "SR Torm", "type": "tormentor", "x1": 30, "y1": 2, "x2": 30, "y2": 2}
check("a ladder is vertical", P.is_vertical(_lad), True)
check("so is a tormentor", P.is_vertical(_torm), True)

# ⭐ §2.3.2: "on onstage booms or other vertical hanging positions... from top to
# bottom, DOWNSTAGE TO UPSTAGE." The second clause is the tiebreak, and it is
# what a ladder needs — units hang on both sides of the frame at the same height,
# which without a tiebreak is an arbitrary order.
_lu = [{"unit": 99, "position": "SL Ladder 1", "height": h, "y": y}
       for h, y in [(10, 13), (10, 15), (6, 13), (14, 14)]]
P.number(_lu, _lad)
_by = {i["unit"]: (i["height"], i["y"]) for i in _lu}
check("unit 1 is the highest", _by[1], (14, 14))
check("same height: DOWNSTAGE first", _by[2], (10, 13))
check("...then upstage", _by[3], (10, 15))
check("then the next height down", _by[4], (6, 13))

# A ladder hangs: asking it for a boom base is asking for hardware that does not
# exist. What it needs is a trim.
check("a ladder with no trim is caught",
      any("needs a TRIM" in m for m in
          P.check_booms({"positions": [dict(_lad, trim=None)], "instruments": []})), True)
check("a ladder WITH a floor mount is questioned",
      any("does not stand on the floor" in m for m in
          P.check_booms({"positions": [dict(_lad, mount="boom-base")],
                         "instruments": []})), True)
check("a tormentor is asked for nothing — it is bolted to the building",
      P.check_booms({"positions": [_torm], "instruments": []}), [])

# §2.3.2 FOH rules.
check("a box boom WITH extent numbers from centerline",
      P.number_from({"name": "BB", "type": "box-boom", "x1": 2, "y1": -9,
                     "x2": 9, "y2": -9}), "CENTER")
check("...but a box boom hung as a plain pipe falls back to top-down",
      P.number_from({"name": "BB", "type": "box-boom", "x1": 2, "y1": -9,
                     "x2": 2, "y2": -9}), "TOP")
check("an FOH position parallel to centerline numbers from the plaster line",
      P.number_from({"name": "FOH R", "x1": 28, "y1": -4, "x2": 28, "y2": -20,
                     "type": "pipe", "foh": True}), "PLASTER")

# ⭐ CHANNELS are a different thing and the standard does not cover them. RP-2
# requires a channel to be shown and says channel hookups are "not addressed in
# this document." Jerry's convention, 2026.09.23: house left to house right — so
# channel 1 is at STAGE RIGHT, the maximum x.
#
# That is the REVERSE of RP-2's unit numbering across the same batten, and it is
# deliberate: a unit number is read by someone under the pipe with a wrench, a
# channel by someone in the house reading the plot. Different readers, and they
# are allowed to run different ways.
_ch = [{"unit": 1, "x": 5.0}, {"unit": 2, "x": 22.0}, {"unit": 3, "x": 30.0}]
check("channels run house left to house right — stage right first",
      [i["x"] for i in P.channel_order(_ch)], [30.0, 22.0, 5.0])
check("...which is the opposite of the unit order", P.CHANNEL_FROM, "SR")
check("...and the legend says the standard is silent on it",
      "does not address channels" in P.channel_note(), True)


print("\nthe section: ONE governing luminaire per position, aimed the real way")
import plot_to_section as _sec

# ⭐ RP-2 §3: "Scaled representation of the luminaire that DETERMINES batten
# height mounted in each position." One per position, not every unit — drawing
# all sixty turns the section into a smear and hides the only thing it is for.
_on = [{"unit": 1, "x": 5.0, "y": 20.0}, {"unit": 2, "x": 16.5, "y": 20.0},
       {"unit": 3, "x": 28.0, "y": 20.0}]
check("the unit nearest the cut governs",
      _sec.governing_unit(_on, 16.5)["unit"], 2)
check("a cut at stage left picks the stage-left unit",
      _sec.governing_unit(_on, 1.0)["unit"], 1)
# Which unit constrains a trim is a judgment, so the designer can name it.
check("an explicit `governing` flag wins",
      _sec.governing_unit([dict(_on[0], governing=True)] + _on[1:], 16.5)["unit"], 1)
check("no units, no luminaire", _sec.governing_unit([], 16.5), None)

# 🔴 The rotation must come from the real direction vector, not from the
# elevation. Elevation is UNSIGNED — 40° describes both "down and upstage" and
# "down and downstage" — so deriving a rotation from it aims half the rig
# backwards, and a section whose instruments point somewhere they do not is
# worse than no section.
import math as _m

def _nose(trim, here, target, head_h=5.5):
    rot = _m.degrees(_m.atan2(head_h - trim, target - here)) + 90
    a = _m.radians(rot)
    return round(_m.sin(a), 2), round(-_m.cos(a), 2)

_dx, _dy = _nose(14, 16, 10)
check("aiming downstage points the nose downstage", _dx < 0 and _dy < 0, True)
_dx, _dy = _nose(14, 16, 24)
check("aiming upstage points it upstage", _dx > 0 and _dy < 0, True)
check("aiming straight down points straight down", _nose(14, 16, 16), (0.0, -1.0))

_s, _drawn = _sec.render("../samples/bluver.plot.json",
                         __import__("tempfile").mkstemp(suffix=".pdf")[1])
# ⚠ Derived from the plot, not hardcoded. This asserted `3`, which was the
# number of horizontal positions the sample happened to have — so adding a pipe
# to the sample failed a test about the SECTION. The property is one governing
# luminaire per horizontal position that carries units; count those.
_secplot = _json.load(open("../samples/bluver.plot.json"))
_hasunits = {(i.get("position") or "").strip().lower() for i in _secplot["instruments"]}
_horiz = [q for q in _secplot["positions"]
          if not P.is_vertical(q) and (q.get("name") or "").strip().lower() in _hasunits]
check("every horizontal position with units gets exactly one",
      len(_drawn), len(_horiz))
check("...and the section draws without clipping", _s.warnings, [])


print("\nthe unit number goes INSIDE the body, and follows the symbol round")
# RP-2 §6.14.2 draws the instrument number inside the luminaire body, with the
# wattage below it in the barrel — not in the stack underneath. Jerry asked for
# the same thing 2026.09.23: "move the unit number onto the center of the unit."


class _Recorder:
    """A stand-in Sheet that just remembers where text was written."""
    def __init__(self):
        self.texts = []
    def text(self, x, y, s, **kw):
        self.texts.append((round(x, 3), round(y, 3), str(s)))
    def line(self, *a, **k):
        pass
    def circle(self, *a, **k):
        pass
    def rect(self, *a, **k):
        pass


def _where(label, **kw):
    r = _Recorder()
    sym.notation(r, 0.0, 0.0, **kw)
    return next(((x, y) for x, y, t in r.texts if t == label), None)

# The number goes at the SYMBOL'S CENTRE, which unit() measures per fixture —
# an ERS's centre sits forward of its yoke, a PAR's almost on it.
_C = (lambda lo_hi: (lo_hi[0] + lo_hi[1]) / 2)(sym._extent(sym.for_type("S4 26")))
check("an S4's centre is forward of its yoke", _C < 0, True)

_at0 = _where("7", unit=7, rotate_deg=0.0, body_center=_C)
check("the unit number is drawn", _at0 is not None, True)
check("...at the centre, not the yoke", round(_at0[1], 2) != 0.0, True)
check("...which for an ERS is toward the lens", _at0[1] < 0, True)

# It must follow the symbol round, or it lands outside the body the moment a
# unit is rotated to its focus.
_at90 = _where("7", unit=7, rotate_deg=90.0, body_center=_C)
_at180 = _where("7", unit=7, rotate_deg=180.0, body_center=_C)
check("rotating 90° moves it sideways", abs(_at90[0]) > abs(_at90[1]), True)
check("rotating 180° flips it", _at180[1] > _at0[1], True)
# ⚠ Measure the ALONG-AXIS offset only. There is also a small fixed nudge that
# centres the text on its own baseline, and that one must NOT rotate — the text
# stays horizontal (RP-2 p.1: "the associated text should be properly oriented
# with the rest of the text in the drawing"), so its baseline correction lives
# in page space. Counting it made 0° and 180° look asymmetric when they are not.
_mid = (_at0[1] + _at180[1]) / 2          # the unrotating baseline nudge
check("0° and 180° are symmetric about the baseline nudge",
      round(_at0[1] - _mid, 3), round(-(_at180[1] - _mid), 3))
check("...and neither strays sideways", (_at0[0], _at180[0]), (0.0, 0.0))

# ⚠ NO wattage on the symbol. §6.14.2 shows one, but a recommended practice
# records what MAY be drawn. Jerry, 2026.09.23: "I've never seen it on plots
# except for 750w S4 where the back is blackened — like they have for HMI lamps
# in the spec." The working convention is the shaded rear, drawn instead.
_w0 = _where("575", unit=7, wattage=575, rotate_deg=0.0, body_center=_C)
check("the wattage is NOT drawn on the symbol", _w0, None)
check("the number still clears the pipe at the yoke", abs(_at0[1]) > 0.05, True)

print("\n§6.15's shaded rear — arc sources, and Jerry's 750W mark")
from plotedit.scaled_pdf import _shade_rear_for as _SR

# ⚠ It reads the LAMP, not the fixture: the same Source Four is a 575 or a 750
# depending on what is in it, so shading by type would mark the whole rig or none.
check("a 750 gets the mark", _SR("S4 26", "HPL 750"), True)
check("a 575 does not", _SR("S4 26", "HPL 575"), False)
check("an unstated lamp does not — it is a 575", _SR("S4 26", None), False)
check("the long-life 575X does not either", _SR("S4 36", "HPL 575X"), False)
check("an LED does not", _SR("Lustr 26 EDLT", None), False)

_body = sym.for_type("S4 26")
_sh = sym.shade_rear(_body)
check("the shade is one filled polygon", (len(_sh), _sh[0][0]), (1, "fill"))
_lo, _hi = sym._extent(_body)
_pts = _sh[0][1]
check("...covering the BACK of the body, not the lens",
      min(a for a, _ in _pts) > (_lo + _hi) / 2, True)
check("...and reaching the very back", round(max(a for a, _ in _pts), 2), round(_hi, 2))

# radius() must cope with the new primitive. The old version treated anything
# that was not a poly or a line as a single POINT, so "fill" made it try to
# unpack a whole list as one (a, c) pair — a fall-through default is a bug
# waiting for the next primitive.
check("radius() handles a fill prim", sym.radius(_sh + list(_body)) > 0, True)

# ⭐ ONE MARK, TWO MEANINGS — §6.15 says arc source, Jerry says 750W lamp. So the
# key must say which, and only when the plot actually uses it.
# Imported here rather than relying on where else in this file it happens to be
# bound — a test that depends on the order of unrelated sections is a test that
# breaks when someone reorders them.
from plotedit import key as _key
import json as _js
_p = _js.load(open("../samples/bluver.plot.json"))
check("the key explains the mark when it is used", _key.shaded_used(_p), True)
check("...and does not when it is not",
      _key.shaded_used({"instruments": [{"type": "S4 26", "lamp": "HPL 575"}]}), False)


print("\nthe instrument is drawn as if it sits ABOVE the pipe")
# Jerry, 2026.09.23: "the instrument has to be drawn so that the pipe does not go
# through it — as if the instrument is above it, even though it's not." Two
# payoffs: the symbol reads as one object, and the body becomes white space the
# unit number can live in.


class _Order:
    """Records the ORDER of drawing calls, which is what occlusion depends on."""
    def __init__(self):
        self.calls = []
    def fill_poly(self, pts, **k):
        self.calls.append(("fill", len(pts)))
    def line(self, *a, **k):
        self.calls.append(("line", None))
    def circle(self, *a, **k):
        self.calls.append(("circle", None))
    def text(self, *a, **k):
        self.calls.append(("text", None))


_o = _Order()
sym.draw(_o, sym.for_type("S4 26"), 0, 0)
_kinds = [k for k, _ in _o.calls]
check("the body is filled", "fill" in _kinds, True)
# ⭐ Every fill must come BEFORE every stroke, or the paint covers the outline.
check("...before anything is stroked",
      max(i for i, k in enumerate(_kinds) if k == "fill")
      < min(i for i, k in enumerate(_kinds) if k != "fill"), True)

# Only CLOSED shapes are filled — an open outline has no inside, and filling it
# would paint a wedge of white across the drawing.
_o2 = _Order()
sym.draw(_o2, [("poly", [(0, 0), (1, 0), (1, 1)], False)], 0, 0)
check("an open poly is NOT filled", [k for k, _ in _o2.calls].count("fill"), 0)

# A sheet without fill_poly must still draw — the section and any other caller
# should degrade to outlines rather than raise.
class _NoFill:
    def line(self, *a, **k): pass
    def circle(self, *a, **k): pass
    def text(self, *a, **k): pass
try:
    sym.draw(_NoFill(), sym.for_type("S4 26"), 0, 0)
    _ok = True
except Exception:
    _ok = False
check("a sheet with no fill_poly still draws", _ok, True)


print("\na break mark: the pipe continues, but not all of it is drawn")
from plotedit.scaled_pdf import compress_heights as _C

# ⭐ RP-2 §6.12's Option 1 plate compresses the boom and marks it with a break.
# Jerry pointed at it 2026.09.23: "that means the whole boom isn't there, i.e.
# the whole length isn't being represented."

# A shin/mid/head boom fits as it is — nothing to gain, so no break.
_ys, _b, _top = _C([2, 4, 8])
check("a short boom is drawn true", _ys, [2.0, 4.0, 8.0])
check("...with no break", _b, [])

# A tall one is compressed and marked.
_ys, _b, _top = _C([4.5, 8, 12])
check("a tall boom is compressed", _ys[-1] < 12, True)
check("...and carries exactly one break", len(_b), 1)
check("...placed in the empty run it removed", 0 < _b[0] < _ys[0], True)

# ⚠ Order and spacing between CLOSE units must survive untouched — compression
# is allowed to remove empty pipe, never to reorder or squeeze the rig.
check("units stay in order", _ys, sorted(_ys))
check("the 8'-to-12' gap is untouched", round(_ys[2] - _ys[1], 2), 4.0)

# ⚠ It must not break for a trivial saving: a symbol the reader has to stop and
# interpret costs more than half a foot of paper.
check("a 3' run is not worth a break", _C([3, 5])[1], [])

# 🔴 And the heights themselves are never touched. The break says the PAPER is
# compressed; it never says a number is approximate.
_true = [4.5, 8, 12]
_ys, _, _ = _C(_true)
check("compression returns drawn positions, not modified heights",
      _true, [4.5, 8, 12])
check("...and one drawn position per unit", len(_ys), len(_true))
check("an empty boom does not crash", _C([])[0], [])


print("\nthe instrument key — RP-2 §5.1, and only what is ON the plot")
from plotedit import key as _K
import json as _json

_plot = _json.load(open("../samples/bluver.plot.json"))
_types = _K.types_used(_plot)
check("one row per fixture type", len(_types), 5)
# Ordered BY FIXTURE, smallest lens first — how a reader looks something up,
# and how Jerry wrote it: "1) S4 19, 3) S4 26, 2) S4 36".
_names = [r["name"] for r in _types]
check("ordered by fixture, not by count",
      [n for n in _names if n.startswith("S4 ") and n[3:].isdigit()],
      ["S4 19", "S4 26", "S4 36"])
check("the counts add up to the rig",
      sum(r["count"] for r in _types), len(_plot["instruments"]))

# ⚠ Beam and field are NOT on the key — Jerry, 2026.09.23. §5.1 agrees: it asks
# for beam spread only "if the numeric value is not part of the luminaire's
# name", and "S4 26" carries it. The measured angles stay in the fixture table
# for anything that computes; a key is for reading shapes, not for photometrics.
_s426 = next(r for r in _types if r["name"] == "S4 26")
check("the angles are still available to the data model",
      (_s426["field"], _s426["beam"]), (25.0, 18.0))
# ⚠ Wattage is a DELIBERATE departure from §5.1, which asks for "wattage (total
# luminaire load) and/or ANSI lamp code" in the key. Jerry, 2026.09.23: "we can
# lose the wattage too, that will be on the instrument schedule." A key that
# repeats the schedule is a second place for the same fact to go stale. It stays
# in the data model, and on the plot symbols themselves, per §6.14.2.
check("wattage stays available to the data model", _s426["watts"], 575.0)

# §5.1: colour manufacturer designations — but only the ones actually used. A
# key explaining L = Lee on a plot with no Lee in it teaches a reader something
# they do not need.
# ⚠ Compared against the plot's own colours, not a hardcoded list. This asserted
# ["R52+R119"], which was every colour the sample happened to use — so adding
# one instrument in R64 failed a test about the KEY. The property is: each
# colour once, and only the ones actually hung.
_used = _K.colors_used(_plot)
_intheplot = {i["color"] for i in _plot["instruments"] if i.get("color")}
check("colours are listed once each", sorted(_used), sorted(_intheplot))
check("...with no repeats", len(_used), len(set(_used)))
check("...and nothing that is not hung", set(_used) - _intheplot, set())
check("only the makers used are expanded", _K.makers_used(_plot), ["Rosco"])
check("no Lee on a plot with no Lee",
      "Lee" in _K.makers_used(_plot), False)
check("a Lee gel would bring Lee in",
      _K.makers_used({"instruments": [{"color": "L201"}]}), ["Lee"])

# §5.1: accessories get their symbols in the key.
check("accessories are gathered", sorted(_K.accessories_used(_plot)),
      ["4-way barn door", "gobo", "top hat"])

# ⚠ A type the tool cannot identify must be FLAGGED in the key, not quietly
# given no angle — the key is what a stranger reads instead of asking.
_unknown = _K.types_used({"instruments": [{"type": "Zarg 9000"}]})
check("an unknown fixture is marked unknown", _unknown[0]["unknown"], True)
check("...and still appears in the key", _unknown[0]["count"], 1)


print("\na label left of a line must END before it, not start there")
# Jerry, 2026.09.24: "the heights shown on the booms are currently on top of the
# booms — it's hard to read." The labels were placed 4" clear of the pipe and
# drawn LEFT-aligned, so the text grew rightwards straight across it. Anchoring
# the END of the string is the only fix; moving it left just delays the collision
# for longer numbers.
#
# ⚠ Measured from the RENDERED PDF. Alignment is not visible in the call — both
# versions "draw text at x" — so only the output can show which side it grew.
import tempfile as _tf, os as _os
from plotedit.scaled_pdf import Sheet as _Sh, ft as _ft
import fitz as _fitz

_d = _tf.mkdtemp()
_path = _os.path.join(_d, "align.pdf")
# ⭐ At the PLOT'S OWN SCALE. The first version of this test used 1" = 1'-0",
# where 5 inches of clearance is 30 points and a 6pt label is about 20 wide — so
# nothing collided and the test proved nothing. At 1/4" that same 5 inches is
# SEVEN points, and the label runs clean across the pipe. A test has to
# reproduce the condition, not an easier version of it.
_s = _Sh(_path, page="LETTER", scale="1/4", show="align test")
_s.origin(_ft(2), _ft(2))
_s.line(12, 0, 12, 20, width=2)                   # a vertical "pipe" at x = 12
_s.text(12 - _ft(0, 5), 14, "12'-0\"", size=6, align="right")
_s.text(12 - _ft(0, 5), 6, "12'-0\"", size=6)     # left-aligned, the old way
_s.finish()

_pg = _fitz.open(_path)[0]
_hits = _pg.search_for("12'-0\"")
check("both labels rendered", len(_hits), 2)
_pipe_x = _pg.search_for("12'-0\"")  # placeholder to keep names obvious
# the pipe sits at 4 ft from the origin; find it from the drawing instead
_lines = [d["rect"] for d in _pg.get_drawings() if d["rect"].width < 3]
_px = min((r.x0 for r in _lines if r.height > 50), default=None)
check("the pipe was found", _px is not None, True)
_right, _left = sorted(_hits, key=lambda r: r.y0)          # right-aligned is higher up
check("the right-aligned label ends BEFORE the pipe", _right.x1 <= _px + 1, True)
check("...while the left-aligned one crosses it", _left.x1 > _px, True)


print("\nmoving a pipe moves its rig — the trim is in two places")
# 🔴 Found 2026.09.24 by editing a trim in the browser and watching nothing
# happen. The label read "GRID C — trim 18'-0"" while every unit on it went on
# computing from 14: two places held the same fact and only one was read, so the
# drawing could STATE one trim and COMPUTE another.
_tp = {"positions": [{"name": "E1", "type": "electric", "x1": 0, "y1": 16,
                      "x2": 33, "y2": 16, "trim": 14}],
       "instruments": [{"unit": 1, "position": "E1", "trim": 14},
                       {"unit": 2, "position": "E1", "trim": 14}]}
check("a plot in agreement reports nothing", P.trim_conflicts(_tp), [])
_moved = P.apply_trim(_tp, "E1", 18)
check("raising the pipe moves every unit", _moved, 2)
check("...to the new height", [i["trim"] for i in _tp["instruments"]], [18.0, 18.0])
check("...and nothing is left in conflict", P.trim_conflicts(_tp), [])

# A unit hung below its pipe is legal — a sidearm, a drop-arm — so this reports
# rather than corrects. But it must REPORT: the silent version is a plot whose
# printed trim is a lie.
_tp["instruments"][0]["trim"] = 12.0
check("a deliberate drop is reported, not corrected",
      len(P.trim_conflicts(_tp)), 1)
check("...naming the unit", "unit 1" in P.trim_conflicts(_tp)[0], True)

# ⚠ And the offset survives the next move: a drop-arm stays a drop-arm.
P.apply_trim(_tp, "E1", 20)
check("a deliberate offset is carried, not flattened",
      sorted(i["trim"] for i in _tp["instruments"]), [14.0, 20.0])
check("a vertical position is left alone — its units differ by height on purpose",
      P.trim_conflicts({"positions": [{"name": "B", "type": "boom", "x1": 1, "y1": 1,
                                       "x2": 1, "y2": 1, "trim": 12}],
                        "instruments": [{"unit": 1, "position": "B", "trim": 8}]}), [])


print("\ntrims are checked against the ceiling")
# 🔴 Jerry, 2026.09.24: "I guess we need a ceiling height — the ceiling is
# probably closer to 16'." Nothing had been checking. A pipe had just been raised
# to 18' in a room with a 15' grid and the tool drew it, computed footcandles
# from it and printed it, without a word.
_rm = {"room": {"width": 33, "depth": 38, "gridHeight": 16.0},
       "positions": [{"name": "E1", "type": "electric", "x1": 0, "y1": 16,
                      "x2": 33, "y2": 16, "trim": 14.0}],
       "instruments": []}
check("a comfortable trim passes", P.headroom(_rm), [])

_hi = {**_rm, "positions": [dict(_rm["positions"][0], trim=18.0)]}
check("a trim above the ceiling is caught",
      any("cannot be hung" in m for m in P.headroom(_hi)), True)

# A pipe hangs below the grid and the instrument below the pipe — a Source Four
# on a c-clamp is about 20 inches to the lens. 15'-6" under a 16' grid is not
# impossible, it is tight, and the difference matters.
_tight = {**_rm, "positions": [dict(_rm["positions"][0], trim=15.5)]}
_msgs = P.headroom(_tight)
check("a tight trim is flagged but not called impossible",
      len(_msgs) == 1 and "cannot be hung" not in _msgs[0], True)

# ⚠ A FOH position hangs from the HOUSE ceiling, which is usually higher. A
# catwalk at 18' over a room with a 15' stage grid is ordinary — reporting it as
# a fault teaches the reader to ignore the warnings that are real.
# ⚠ FOH is the DESIGNER'S flag in a black box — there is no plaster line for
# geometry to read (Jerry, 2026.09.24), so the catwalk has to say so itself.
# It also sits INSIDE the room now, over the audience at y = 4.
_cat = {**_rm, "positions": [{"name": "Cat 1", "type": "catwalk", "x1": 0,
                              "y1": 4.0, "x2": 33, "y2": 4.0, "trim": 18.0,
                              "foh": True}]}
check("a catwalk is NOT judged against the stage grid",
      any("cannot be hung" in m for m in P.headroom(_cat)), False)
check("...but says it was not checked", any("not checked" in m for m in P.headroom(_cat)), True)
_cat2 = {**_cat, "room": {**_rm["room"], "houseCeiling": 22.0}}
check("...and passes once the house ceiling is known", P.headroom(_cat2), [])
_cat3 = {**_cat, "room": {**_rm["room"], "houseCeiling": 16.0}}
check("...and fails against a LOW house ceiling",
      any("above the HOUSE ceiling" in m for m in P.headroom(_cat3)), True)

# With no ceiling at all, say so rather than passing silently.
_none = {"room": {"width": 33, "depth": 38}, "positions": _rm["positions"], "instruments": []}
check("no ceiling recorded is reported, not passed",
      any("NOT checked against anything" in m for m in P.headroom(_none)), True)
check("...and a plot with no trims stays quiet",
      P.headroom({"room": {}, "positions": [{"name": "E", "x1": 0, "y1": 1,
                                             "x2": 9, "y2": 1}], "instruments": []}), [])

# ---------------------------------------------------------------- the sheet
# ⭐ A drawing that runs off the paper is worse than no drawing, so the guard
# that says so has to be USEFUL. It reported "the sheet holds 40.0' x 58.8'" and
# left the reader to work backwards from two numbers to a paper size — Jerry,
# 2026.09.24: "do we know what size sheet it is referring to?" It did not.
#
# 🔴 And the advice has to be TRUE. "Use a bigger sheet" is not advice; naming a
# sheet that still does not fit is worse than saying nothing, so the sheet the
# message names is rendered and must come out clean.
import re as _re
import tempfile as _tf
import plot_to_pdf as _P

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "bluver.plot.json")
_tmp = _tf.mkdtemp()

def _render(page, landscape, scale):
    sheet, _ = _P.render(_SAMPLE, os.path.join(_tmp, f"{page}-{landscape}-{scale.replace('/','_')}.pdf"),
                         page=page, landscape=landscape, scale=scale)
    return [w for w in sheet.warnings if "CLIPPED" in w]

_over = _render("TABLOID", False, "1/4")
check("a drawing that overruns is reported", bool(_over), True)
_msg = _over[0] if _over else ""
check("...and the message NAMES the sheet", "TABLOID portrait" in _msg, True)
check("...with its size in inches", '11" x 17"' in _msg, True)
check("...and says which edge", "off the RIGHT" in _msg, True)

# The sheet it recommends, rendered. If that still clips, the advice sent the
# reader to buy paper that does not help.
_m = _re.search(r"Or keep .*? on (\w+) (portrait|landscape)", _msg)
check("...and names a sheet to move to", bool(_m), True)
if _m:
    _again = _render(_m.group(1), _m.group(2) == "landscape", "1/4")
    check(f"...and {_m.group(1)} {_m.group(2)} really does fit", _again, [])

# The largest scale it offers, on the ORIGINAL sheet, must also fit.
_s = _re.search(r"fits this sheet: ([\d/]+)\"", _msg)
check("...and names a scale that fits", bool(_s), True)
if _s:
    check(f"...and {_s.group(1)}\" really does fit TABLOID portrait",
          _render("TABLOID", False, _s.group(1)), [])

check("a drawing that fits is not reported", _render("ARCH_D", True, "1/2"), [])

# ⚠ Turn the paper before buying more of it. ARCH D PORTRAIT cannot hold this
# drawing at 1/2", but the same sheet landscape can, and that is the cheaper
# answer — it is already in the plotter.
_rot = _render("ARCH_D", False, "1/2")
check("a sheet that only needs turning says so",
      bool(_rot) and "ARCH_D landscape" in _rot[0], True)

# ---- zoom in as far as the sheet allows
# Jerry, 2026.09.24: "we should be able to zoom in as long as all the objects
# are still on the page."
#
# 🔴 The real test is the BOUNDARY: the chosen scale must fit AND the next one
# up must not. A fitter that always returns 1/8" fits every time and is useless.
_fit_for = lambda page, land: _P.largest_scale(
    lambda k, path: _P.render(_SAMPLE, path, scale=k, page=page, landscape=land)[0])
_best = _fit_for("ARCH_D", True)
check("the fitted scale is a STANDARD one", _best in _P.FIT_SCALES, True)
check(f"...and {_best}\" fits ARCH_D landscape", _render("ARCH_D", True, _best), [])
_up = _P.FIT_SCALES[_P.FIT_SCALES.index(_best) - 1] if _P.FIT_SCALES.index(_best) else None
if _up:
    check(f"...and the next one up ({_up}\") does NOT — so it zoomed in as far as it goes",
          bool(_render("ARCH_D", True, _up)), True)

# A smaller sheet has to come out at a smaller scale, or nothing is being fitted.
_small = _fit_for("TABLOID", False)
check("a smaller sheet fits at a smaller scale",
      _P.FIT_SCALES.index(_small) > _P.FIT_SCALES.index(_best), True)
check(f"...and {_small}\" really fits TABLOID portrait",
      _render("TABLOID", False, _small), [])

# The defaults Jerry asked for, 2026.09.24: "make ARCH D landscape the default".
_sheet, _ = _P.render(_SAMPLE, os.path.join(_tmp, "default.pdf"))
check("the default sheet is ARCH_D", _sheet.page_name, "ARCH_D")
check("...landscape", _sheet.landscape, True)
check("...36in x 24in", [round(v) for v in _sheet.page_in], [36, 24])
check("...and nothing runs off it",
      [w for w in _sheet.warnings if "CLIPPED" in w], [])

# ---------------------------------------------------- whose drawing is this
# 🔴 NOTHING ABOUT WHO MADE IT IS HARDCODED. Jerry, 2026.09.24: "I don't want to
# print anything that is hardcoded about the venue because it will be used for
# other venues — if we want print from the json, that's cool."
#
# The renderer defaulted the designer to "Design: Jerry Jonas" and printed
# "Twin Oaks Studios" in the title-block footer from a string literal, so a plot
# drawn for another designer at another venue came out claiming his authorship.
import fitz as _fz

def _pdf_text(plot_obj, name):
    src = os.path.join(_tmp, name + ".json")
    with open(src, "w") as fh:
        _json.dump(plot_obj, fh)
    out = os.path.join(_tmp, name + ".pdf")
    _P.render(src, out)
    return _fz.open(out)[0].get_text()

_named = _json.load(open(_SAMPLE))
_anon = {k: v for k, v in _named.items() if k not in ("designer", "studio")}

_t = _pdf_text(_anon, "anon")
check("a plot that names nobody prints no designer", "Jerry" in _t, False)
check("...and no studio", "Twin Oaks" in _t, False)
check("...and not a bare 'Design:' either", "Design:" in _t, False)
# The scale bar is only true at actual size, so that instruction always stays.
check("...but still says to print at 100%", "print at 100%" in _t, True)

_t2 = _pdf_text({**_anon, "designer": "A N Other", "studio": "Some Other Shop"},
                "other")
# ⚠ And the LIBRARY's own defaults, not just the path plot_to_pdf takes. That
# path always passes designer= and studio= explicitly, so putting the names back
# as Sheet() defaults left every one of the checks above passing — while any
# other caller (the section, the symbol sheet, anything written later) would
# quietly print them again.
_bare = os.path.join(_tmp, "bare-sheet.pdf")
_sh = Sheet(_bare, show="Anything")
_sh.rect(0, 0, 4, 4)
_sh.finish()
_bt = _fz.open(_bare)[0].get_text()
check("a Sheet made with no names prints none", "Jerry" in _bt or "Twin Oaks" in _bt, False)

check("a plot that names someone prints THEM", "Design: A N Other" in _t2, True)
check("...and their shop", "Some Other Shop" in _t2, True)
check("...and still nobody else", "Jerry" in _t2 or "Twin Oaks" in _t2, False)

# The SECTION fits itself too — it is the drawing trims are read off, so a
# bigger scale is a more useful drawing.
import plot_to_section as _S
_sec_sheet, _ = _S.render(_SAMPLE, os.path.join(_tmp, "sec.pdf"))
check("the section fits its sheet",
      [w for w in _sec_sheet.warnings if "CLIPPED" in w], [])
_sec_up = _S.render(_SAMPLE, os.path.join(_tmp, "sec-up.pdf"), scale="3/4")[0]
check("...and is zoomed in as far as it goes (3/4in clips)",
      any("CLIPPED" in w for w in _sec_up.warnings), True)

print()
print("the build says which build it is")
# ⭐ Jerry, 2026.09.26: "I'd like to print the version number on the UI so they
# know." Testers had no way to say which version they saw something in, and the
# download carried no version information at all — the releases are git tags,
# so a clone knew and the people who never cloned did not.
#
# 🔴 A build must NEVER invent a number. A working copy reporting itself as a
# release sends whoever reads the report hunting in source that is not what was
# running, which costs more than having no version at all.
import os as _os
from plotedit import version as _V

_had = _V._FILE.exists()
_orig = _V._FILE.read_text(encoding="utf-8") if _had else None
try:
    if _had:
        _os.unlink(_V._FILE)
    check("a checkout reports dev, not a number", _V.version(), "dev")
    _V._FILE.write_text("0.1.7\n", encoding="utf-8")
    check("a packaged build reports its tag", _V.version(), "0.1.7")
    _V._FILE.write_text("   \n", encoding="utf-8")
    check("an empty VERSION is dev, not blank", _V.version(), "dev")
    _os.unlink(_V._FILE)
finally:
    if _had:
        _V._FILE.write_text(_orig, encoding="utf-8")

from fastapi.testclient import TestClient as _TC
from plotedit.api import app as _app
check("health carries it so the editor can show it",
      "version" in _TC(_app).get("/health").json(), True)

# ⚠ The workflow is the only thing that writes VERSION, and nothing else would
# notice if that line were dropped — the package would just quietly go back to
# saying "dev" on every release.
_wf = open(_os.path.join(_os.path.dirname(__file__), "..",
                         ".github", "workflows", "release.yml"),
           encoding="utf-8").read()
check("the release workflow writes VERSION into the package",
      "out/plotedit/server/plotedit/VERSION" in _wf, True)
check("...from the tag, and only on a tag build",
      'GITHUB_REF_TYPE}" = "tag"' in _wf and "GITHUB_REF_NAME#v" in _wf, True)

# 🔴 And it must never be committed. A checkout carrying a VERSION file would
# claim a release it is not.
_ign = open(_os.path.join(_os.path.dirname(__file__), "..", ".gitignore"),
            encoding="utf-8").read()
check("VERSION is gitignored", "server/plotedit/VERSION" in _ign, True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
