#!/usr/bin/env python3
"""Step 5: everything that leaves the editor, and the ground plan coming in.

    cd server && python3 test_export.py
"""
import json
import os
import sys

from fastapi.testclient import TestClient

from plotedit.api import app
from plotedit import exports

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "samples", "bluver.plot.json")
plot = json.load(open(SAMPLE))
client = TestClient(app)
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<50} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def _fails_with(fn, exc):
    """Did this raise the exception it should have?"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


print("schedule — hanging order")
sched = exports.schedule_csv(plot).splitlines()
# ⚠ The report ends with a blank line and a TOTAL LOAD row, so the data stops
# before them. Slicing to the end used to be the same thing and is not any more.
_end = next(k for k, r in enumerate(sched) if r.startswith("TOTAL LOAD"))
rows = [r.split(",") for r in sched[5:_end] if r.strip()]
check("every instrument present", len(rows), len(plot["instruments"]))
check("sorted by position then unit", [r[0] for r in rows][:4],
      ["GRID B", "GRID B", "GRID C", "GRID C"])
# Look the column up by NAME. A hard-coded index breaks the moment a column is
# inserted — which is exactly what adding Circuit did, and the failure read as
# "color is empty" rather than "the columns moved".
_col = exports.SCHEDULE_COLUMNS.index
check("color survives the CSV", rows[2][_col("Color")], "R52+R119")
check("the circuit column exists", "Circuit" in exports.SCHEDULE_COLUMNS, True)
check("circuit sits beside channel, not beside address",
      _col("Circuit") - _col("Channel"), 1)

print("\nhookup — channel order")
_hlines = exports.hookup_csv(plot).splitlines()
_hend = next(k for k, r in enumerate(_hlines) if r.startswith("TOTAL LOAD"))
hook = [r.split(",") for r in _hlines[5:_hend] if r.strip()]
check("channels ascend", [int(r[0]) for r in hook], sorted(int(r[0]) for r in hook))
check("starts at channel 1", hook[0][0], "1")

print("\nmagic sheet")
groups = exports.magic_sheet_rows(plot)
bax = next(g for g in groups if g["purpose"] == "BAX")
check("BAX grouped", bax["channels"], [11, 12, 13, 14])
check("BAX has no color, as in the archive", bax["colors"], [])

print("\neos patch — the format is UNVERIFIED and must say so")
asc = exports.eos_patch(plot)
check("warning is in the file itself", "HAS NOT BEEN TESTED" in asc, True)
check("unpatched units are listed, not dropped", asc.count("! Not patched") , 1)
# Count from the data, not from a number typed here — adding a boom to the
# sample broke this once already, and the failure read as "the exporter dropped
# units" rather than "the sample grew."
# Match the line's SHAPE, not a position name. The original counted lines
# starting "!   GRID", which quietly stopped counting when the sample gained
# booms — and the failure read as "the exporter dropped units" rather than "the
# sample grew a position whose name does not start with GRID".
import re as _re
check("every unit is listed as unpatched — the sample has no addresses",
      len(_re.findall(r"^!   .+ unit \d+ .* ch=", asc, _re.M)),
      len(plot["instruments"]))

print("\nexport endpoints")
req = {"plot": plot}
# ⚠ /export/eos is NOT in this list, and that is the point. The sample has no
# addresses, so its patch would be empty, and an empty patch is refused now —
# see "an empty patch is refused" below. This loop used to assert it returned
# 200 with a valid header, which was true and was exactly the bug: the file was
# well formed, imported into Eos without complaint, and patched nothing.
for path, kind, sniff in [("/export/schedule", "text/csv", b"Instrument Schedule"),
                          ("/export/hookup", "text/csv", b"Channel Hookup")]:
    r = client.post(path, json=req)
    check(f"{path} 200", r.status_code, 200)
    check(f"{path} content", sniff in r.content, True)
    check(f"{path} is a download", "attachment" in r.headers.get("content-disposition", ""), True)

# ⭐ The sample carries booms, whose elevations sit beside the plot, and a FOH
# catwalk over the house. ASKED FOR Tabloid at 1/4" it does not fit — and the
# right behaviour is to REFUSE, not to clip. That is the guard working.
r = client.post("/export/pdf", json={**req, "page": "TABLOID",
                                     "landscape": False, "scale": "1/4"})
check("a plot with booms will not fit Tabloid at 1/4", r.status_code, 422)
_detail = r.json()["detail"]
check("...and the refusal says which EDGE it runs off",
      any(w in _detail for w in ("LEFT", "RIGHT", "TOP", "BOTTOM")), True)
check("...and NAMES the sheet, so nobody has to work it out from two numbers",
      "TABLOID portrait" in _detail, True)

# ⭐ But the DEFAULTS are ARCH D landscape at the largest standard scale that
# fits (Jerry, 2026.09.24), so an export asked for nothing in particular just
# works — and comes out zoomed in as far as the sheet allows, not at some
# cautious minimum.
r = client.post("/export/pdf", json=req)
check("/export/pdf 200 with no page or scale asked for", r.status_code, 200)
check("/export/pdf is a PDF", r.content[:5], b"%PDF-")
import fitz as _fitz
_d = _fitz.open(stream=r.content, filetype="pdf")
check("...on ARCH D landscape, 36in x 24in",
      [round(_d[0].rect.width / 72), round(_d[0].rect.height / 72)], [36, 24])
check("...at 1/2in = 1ft, not the old 1/4in", 'Scale 1/2" = 1\'-0"' in _d[0].get_text(), True)

r = client.post("/export/pdf", json={"plot": plot, "page": "ARCH_D",
                                     "landscape": True})
check("/export/pdf 200 on the sheet Jerry actually draws on", r.status_code, 200)
check("/export/pdf is a PDF", r.content[:5], b"%PDF-")

r = client.post("/export/dxf", json=req)
check("/export/dxf 200", r.status_code, 200)
check("/export/dxf is a DXF", b"SECTION" in r.content[:2000], True)

print("\na plot that will not fit must FAIL, not clip")
# ⚠ Asked for TABLOID landscape explicitly. This used to rely on the DEFAULTS
# being tabloid, so when the defaults moved to ARCH D the export succeeded and
# the test asserted a 422 against a PDF — and then tried to read that PDF as
# JSON, which is how it announced itself. A test of the guard should name the
# sheet it is testing.
r = client.post("/export/pdf", json={"plot": plot, "page": "TABLOID",
                                     "landscape": True, "scale": "1/4"})
check("landscape tabloid at 1/4 is refused", r.status_code, 422)
check("and names which edge it runs off",
      any(w in r.json()["detail"] for w in ("LEFT", "RIGHT", "TOP", "BOTTOM")), True)

# ⚠ Refuse only what makes the drawing WRONG. A grazing pool is a true note
# ABOUT the plot, not a reason to withhold the plot — refusing over it would
# mean a rig with one flat side light could never be exported at all.
r = client.post("/export/pdf", json={"plot": plot, "page": "ARCH_D", "landscape": True})
check("a non-fatal note does not block the export", r.status_code, 200)
check("...and travels back in a header", "X-Plot-Notes" in r.headers, True)
check("...naming the unit it is about", "unit" in r.headers.get("X-Plot-Notes", ""), True)

print("\ndxf import")

def make_venue_dxf(path):
    """A stand-in for what a venue sends: inches, walls, a grid, a door swing.
    Built fresh every run — a test must not read whatever is lying in out/."""
    import ezdxf
    d = ezdxf.new("R2010"); d.header["$INSUNITS"] = 1
    for L in ("WALLS", "GRID", "DOORS"):
        d.layers.add(L)
    m = d.modelspace(); W, D = 33 * 12, 38 * 12
    m.add_lwpolyline([(0, 0), (W, 0), (W, D), (0, D)], close=True, dxfattribs={"layer": "WALLS"})
    for y in range(48, D, 48):
        m.add_line((0, y), (W, y), dxfattribs={"layer": "GRID"})
    m.add_arc((W, 60), 36, 90, 180, dxfattribs={"layer": "DOORS"})
    d.saveas(path)

import tempfile
_tmp = tempfile.TemporaryDirectory()
venue = os.path.join(_tmp.name, "venue.dxf")
make_venue_dxf(venue)

with open(venue, "rb") as fh:
    r = client.post("/import/dxf/layers", files={"file": ("venue.dxf", fh, "application/dxf")})
check("layers listed", [l["name"] for l in r.json()["layers"]], ["DOORS", "GRID", "WALLS"])
check("units read from the header", r.json()["units"], "inches")

with open(venue, "rb") as fh:
    r = client.post("/import/dxf", files={"file": ("venue.dxf", fh, "application/dxf")},
                    data={"layers": "WALLS", "units": "in"})
g = r.json()
check("only the requested layer comes in", len(g["paths"]), 1)
check("inches converted to feet", g["extents"], [0.0, 0.0, 33.0, 38.0])

r = client.post("/import/dxf", files={"file": ("x.dxf", b"not a dxf", "application/dxf")})
check("a bad file is refused with a reason", r.status_code, 400)

print("\nthe load is on the schedule and the hookup")
# ⭐ Jerry, 2026.09.24: "let's add the load (wattage) to the instrument schedule
# and channel report." The schedule had HAD a Wattage column all along — it read
# inst["wattage"], a field nothing ever fills, so every row came out blank while
# photometrics.watts_for() knew the answer.
_sched = exports.schedule_csv(plot)
_hook = exports.hookup_csv(plot)
check("the schedule still has a Wattage column", "Wattage" in _sched.splitlines()[4], True)
check("...and it is no longer empty", ",575," in _sched, True)
check("the hookup has a Watts column now", "Watts" in _hook.splitlines()[4], True)
check("...and it is filled", ",575," in _hook, True)
check("both carry a total", "TOTAL LOAD" in _sched and "TOTAL LOAD" in _hook, True)

# 🔴 UNKNOWN IS NEVER ZERO, and a total beside unknown units says so. A blank
# cell in a load column reads as "nothing on that circuit" — the one wrong
# answer that matters, because it is how a dimmer is loaded past its rating on
# paper and trips in the room.
_mixed = {**plot, "instruments": [
    {"unit": 1, "channel": 1, "type": "S4 26", "position": "P"},
    {"unit": 2, "channel": 2, "type": "Not A Real Fixture", "position": "P"},
]}
_m = exports.schedule_csv(_mixed)
check("a fixture with no wattage says UNKNOWN", "UNKNOWN" in _m, True)
check("...never a blank cell", ",,," in _m.splitlines()[6].split("Not A Real Fixture")[1][:6], False)
check("...and the total counts only what it knows", "TOTAL LOAD,575 W,1 of 2 units" in _m, True)
check("...and says the total is incomplete", "INCOMPLETE" in _m, True)
check("...in grammar a reader does not trip over", "1 unit has no wattage" in _m, True)

# ⚠ An explicit wattage on the instrument WINS. It is the only way to say "this
# one has a 750 in it" about a fixture whose family says 575 — and the plot
# draws that unit with a blackened rear, so a computed figure overriding it
# would put the paperwork and the drawing in contradiction.
_override = {**plot, "instruments": [
    {"unit": 1, "channel": 1, "type": "S4 26", "position": "P", "wattage": 750}]}
check("an explicit wattage beats the computed one",
      "TOTAL LOAD,750 W" in exports.schedule_csv(_override), True)

print("\na ground plan out of a PDF")
# ⭐ Jerry, 2026.09.24: "could we do the same for PDFs too?" A PDF is what comes
# back when you ask a house for its plan — it is what their drawing office
# exports for everybody.
#
# ⭐ THE TEST IS A ROUND TRIP THROUGH OUR OWN DRAWING. Render the sample plot at
# a known scale and read it back: a 33' x 38' room has to come out 33' x 38'.
# Nothing else checks the paper-to-feet arithmetic end to end, and that
# arithmetic IS the feature — the rest is file handling.
import tempfile as _tf2
from plotedit import pdf_bridge as _pdf
import plot_to_pdf as _P2

_pdfpath = os.path.join(_tf2.mkdtemp(), "plan.pdf")
_P2.render(SAMPLE, _pdfpath, page="ARCH_D", landscape=True, scale="1/2")

_pages = _pdf.pages(_pdfpath)
check("the page is found", len(_pages), 1)
check("...and its vector count is reported", _pages[0]["items"] > 500, True)

_got = _pdf.paths(_pdfpath, page=1, scale="1/2")
_room = [p for p in _got["paths"]
         if 32.5 < max(q[0] for q in p["points"]) - min(q[0] for q in p["points"]) < 33.5
         and 37.5 < max(q[1] for q in p["points"]) - min(q[1] for q in p["points"]) < 38.5]
check("a 33x38 room comes back 33x38", len(_room) >= 1, True)

# 🔴 THE SCALE IS NOT IN THE FILE, and getting it wrong is not an error — it is a
# believable drawing of a different building. The same page read at 1/4" is
# exactly twice the size, silently. That is why the importer reports the extents
# and tells the reader to check them against something they measured.
_half = _pdf.paths(_pdfpath, page=1, scale="1/2")["extents"]
_quarter = _pdf.paths(_pdfpath, page=1, scale="1/4")["extents"]
check("the wrong scale gives a plausible wrong answer, not an error",
      round(_quarter[2] / _half[2], 3), 2.0)

# 🔴 y IS FLIPPED on the way in. fitz measures DOWN from the top of the page; a
# plot measures UP from the bottom. Without the flip a symmetrical ground plan
# looks entirely reasonable until somebody hangs the front of house over the
# back wall.
#
# ⚠ Tested on the TRANSFORM, not on the imported file. My first version checked
# that the imported drawing sat above the origin — which it does either way,
# because the bounding box is moved to the origin afterwards. It passed with the
# flip deleted. A test that cannot fail is worse than none, because it is
# counted.
import fitz as _fz
_line = ("l", _fz.Point(10, 20), _fz.Point(10, 30))
check("a line near the TOP of a 100pt page comes out near the top",
      _pdf._flatten(_line, 100.0), [[(10, 80.0), (10, 70.0)]])
_rect = ("re", _fz.Rect(0, 0, 10, 10), 1)
check("...and a rect at the top of the page does too",
      max(q[1] for q in _pdf._flatten(_rect, 100.0)[0]), 100.0)

# ⚠ And the drawing is moved to the ORIGIN, because a PDF's origin is the corner
# of the PAPER, not of the building — leaving it alone puts the plan wherever
# the sheet margin pushed it, which is feet away at any normal scale.
_page_origin = _pdf.paths(_pdfpath, page=1, scale="1/2", origin="page")["extents"]
check("bounding-box import starts at 0,0", [_half[0], _half[1]], [0.0, 0.0])
check("...and page-origin import does not",
      _page_origin[0] > 0.1 and _page_origin[1] > 0.1, True)

check("a page that is not there is refused",
      _fails_with(lambda: _pdf.paths(_pdfpath, page=7), ValueError), True)
check("a scale it does not know is refused",
      _fails_with(lambda: _pdf.paths(_pdfpath, scale="1/7"), KeyError), True)


print()
print("the Eos patch survives an address nobody has decided yet")
# 🔴 Jerry hit this in the editor, 2026.09.26: Export → Eos patch on a plot
# whose two LED addresses read "PENDING — Art, universe 2" returned a 500. The
# address went straight to int() and took the whole export down.
#
# ⚠ Writing a note where an address goes is the RIGHT thing to do when nobody
# has decided it — the plot is honest and the exporter was not. A unit whose
# address is undecided belongs in the NOT PATCHED list beside the ones with no
# address at all, with the reason, not in a traceback.
from plotedit.exports import _addr_text, _unpatchable

_pending = {"unit": 61, "channel": 61, "type": "SHEHDS 19",
            "address": "PENDING — Art, universe 2", "position": "GRID C"}
_plot = {"show": "crash probe", "venue": "", "revision": "0",
         "room": {"width": 30, "depth": 30}, "positions": [],
         "instruments": [
             _pending,
             {"unit": 1, "channel": 1, "type": "S4 26", "address": 45, "position": "E1"},
             {"unit": 2, "channel": 2, "type": "S4 36", "address": "2/12", "position": "E1"},
             {"unit": 3, "channel": 3, "type": "S4 26", "address": None, "position": "E1"},
         ]}

_asc = exports.eos_patch(_plot)          # this is the line that used to raise
check("an undecided address no longer crashes the export", bool(_asc), True)
check("...it is listed as not patched, with the reason",
      any("PENDING" in l and "not a number" in l for l in _asc.splitlines()), True)
check("a plain address still patches", "   1<45" in _asc, True)
# ⚠ 2/12 is not 2 divided by 12 and it is not 212. A console that takes
# universes needs the slash carried through.
check("universe/address survives as written", "   2<2/12" in _asc, True)
check("no address is still its own reason",
      any("unit 3" in l and "no address" in l for l in _asc.splitlines()), True)
check("only the patchable units reached the patch block",
      len([l for l in _asc.splitlines() if "<" in l and not l.startswith("!")]), 2)

check("a bare number formats as itself", _addr_text("45"), "45")
check("universe notation is normalised, not flattened", _addr_text(" 2 / 12 "), "2/12")
check("a note is refused before it reaches the formatter",
      _unpatchable(61, "PENDING — Art, universe 2") is not None, True)
check("...and a real address is not", _unpatchable(1, "2/12"), None)

# 🔴 The plot that actually caused it. If this file ever stops exporting, the
# bug is back with the exact data that found it.
import os as _os2
_real = _os2.path.join(_os2.path.dirname(__file__), "..", "..", "..",
                       "Documents", "AI Brain", "My-AI-Brain", "My AI Brain",
                       "my-files (knowledge)", "plotedit-demo-data",
                       "2026.09.25 - Inferno Productions - Without Consent - Light Plot.plot.json")
if _os2.path.exists(_real):
    _rp = json.load(open(_real))
    check("the plot that found it exports too", bool(exports.eos_patch(_rp)), True)
else:
    print("  --   the demo plot is not on this machine; skipped")


print()
print("an address and a dimmer are alternatives, not a pair")

# ⭐ Jerry, 2026.09.26: "if there is an address there doesn't need to be a
# dimmer or vice versa." A conventional unit in a dimmer-per-circuit house has
# a dimmer and no DMX address of its own. Requiring both would refuse most real
# plots, and USITT ASCII agrees — the classic entry is channel<dimmer.
_mixed = {"show": "Mixed", "instruments": [
    {"unit": 1, "channel": 1, "type": "S4 26", "position": "E1", "address": 45},
    {"unit": 2, "channel": 2, "type": "S4 36", "position": "E1", "dimmer": 17},
    {"unit": 3, "channel": 3, "type": "Lustr 26 EDLT", "position": "E1",
     "address": "2/12", "dimmer": 99},
    {"unit": 4, "channel": 4, "type": "S4 26", "position": "E1"},
]}
_mx = exports.eos_patch(_mixed)
check("a dimmer alone patches", "   2<17" in _mx, True)
check("an address alone patches", "   1<45" in _mx, True)
check("the address wins when a unit has both", "   3<2/12" in _mx, True)
check("...so the dimmer it also carries is not used",
      "   3<99" in _mx, False)
check("neither is still unpatched, and says so",
      any("unit 4" in l and "no address and no dimmer" in l
          for l in _mx.splitlines()), True)

# ⚠ A dimmer is the DMX address only if the racks are addressed 1:1. The file
# has to say which channels came in that way — it is an assumption, not a fact.
check("the file names the channels patched from a dimmer",
      any("channels 2" in l for l in _mx.splitlines()), True)
check("...and does not claim it for the addressed ones",
      any("channels 1" in l for l in _mx.splitlines()), False)

_dimmers_only = {"instruments": [
    {"unit": 1, "channel": 1, "type": "S4 26", "dimmer": 3}]}
check("a plot with only dimmers is NOT refused",
      exports.eos_patch_refusal(_dimmers_only), None)
check("...and the route exports it",
      client.post("/export/eos", json={"plot": _dimmers_only}).status_code, 200)

print()
print("an empty patch is refused, not exported")

# 🔴 THE EXPORT USED TO SUCCEED AND CONTAIN NOTHING. A rig nobody has addressed
# yet produced a valid file with an empty Patch block; Eos imported it without
# complaint and patched nothing. The reason was in a comment at the top of a
# file nobody opens.
_unaddressed = {"show": "No Addresses Yet", "instruments": [
    {"unit": 1, "channel": 1, "type": "S4 26", "position": "GRID A"},
    {"unit": 2, "channel": 2, "type": "S4 26", "position": "GRID A",
     "address": "PENDING — Art, universe 2"},
]}
_why = exports.eos_patch_refusal(_unaddressed)
check("a plot with no addresses is refused", _why is not None, True)
check("...and the reason says the patch would be empty",
      "empty" in (_why or ""), True)
check("...and counts the units it looked at", "2 instruments" in (_why or ""), True)
check("...and tells you either field will do",
      "address or a dimmer" in (_why or ""), True)

check("a plot with no instruments at all is refused too",
      exports.eos_patch_refusal({"instruments": []}) is not None, True)

# One patchable unit is enough — a partial patch is a real patch.
_one = {"instruments": _unaddressed["instruments"] +
        [{"unit": 3, "channel": 3, "type": "S4 26", "address": 12}]}
check("one addressed unit is NOT refused", exports.eos_patch_refusal(_one), None)
# The shipped sample has no addresses either — every tester who opened it and
# tried Export -> Eos patch got an empty file. Left as it is for now; whether the
# sample should carry addresses is a question about what the demo represents.
check("the sample is refused too, and says so",
      "empty" in (exports.eos_patch_refusal(plot) or ""), True)

# The route, which is what the user actually meets.
_r = client.post("/export/eos", json={"plot": _unaddressed})
check("the route refuses with 422", _r.status_code, 422)
# ⚠ Read the body defensively. If the refusal ever stops firing this is a
# FILE, not JSON, and a test that raises here reports a stack trace instead of
# saying which assertion broke.
_detail = _r.json().get("detail", "") if _r.headers.get(
    "content-type", "").startswith("application/json") else ""
check("...and the message reaches the front end",
      "No Eos patch" in _detail, True)
_r2 = client.post("/export/eos", json={"plot": _one})
check("a plot that can be patched still exports", _r2.status_code, 200)

# 🔴 The real plot that cost the evening: every unit unaddressed. Before this
# change it downloaded a file with nothing in it.
if _os2.path.exists(_real):
    check("the plot that lost the evening is now refused",
          exports.eos_patch_refusal(_rp) is not None, True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
