#!/usr/bin/env python3
"""Step 2 test: the read-only service answers, and refuses where it should.

    cd server && python3 test_api.py

Uses FastAPI's TestClient, so no server needs to be running.
"""
import sys

from fastapi.testclient import TestClient

from plotedit.api import app

client = TestClient(app)
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<46} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("health")
check("service answers", client.get("/health").json()["ok"], True)

print("\nfixtures — sources must survive the trip")
fx = client.get("/fixtures").json()
# The count grows as datasheets are fetched. Pin the families instead, so the
# test catches a table that has lost something rather than one that has gained.
check("the table has fixtures", fx["count"] > 40, True)
for _k in ("S4 26", "Lustr 26 EDLT", "ColorSource Spot 26 EDLT", "ColorSource CYC"):
    check(f"{_k} present", _k in fx["fixtures"], True)
check("Lustr key names its lens tube", "Lustr 26 EDLT" in fx["fixtures"], True)
check("source passed through", "EDLT" in fx["fixtures"]["Lustr 26 EDLT"]["source"], True)
check("LED penumbra is tiny", fx["fixtures"]["Lustr 26 EDLT"]["penumbra_deg"], 2.4)
check("tungsten penumbra is not", fx["fixtures"]["S4 26"]["penumbra_deg"], 7.0)

print("\ngels")
g = client.get("/gels").json()
check("the gel table is served whole", g["count"] > 250, True)
check("R119 transmission", g["gels"]["R119"]["transmission"], 0.893)
check("notation explained", set(g["notation"]), {"+", "/"})

print("\ncompute — the values, and the refusals")
r = client.post("/compute", json={"instruments": [
    {"unit": 1, "type": "S4 26", "x": 6, "y": 20, "trim": 14,
     "focus_x": 10, "focus_y": 10, "color": "R52+R119", "lamp": "HPL 575"},
    {"unit": 2, "type": "S4 26", "x": 6, "y": 20},                       # no trim/focus
    {"unit": 3, "type": "Mystery Lantern", "x": 1, "y": 1, "trim": 14,
     "focus_x": 5, "focus_y": 5},                                        # unknown fixture
    {"unit": 4, "type": "S4 26", "x": 6, "y": 20, "trim": 14,
     # ⚠ R64 is a REAL gel Jerry uses on forty units and it is still not in
     # gels.csv. L201 used to stand here and stopped being unknown when LEE
     # landed, which is the right way for this test to break.
     "focus_x": 10, "focus_y": 10, "color": "R64", "lamp": "HPL 575"},   # unknown gel
]}).json()["instruments"]
check("acting-area wash", r[0]["footcandles"], 169)
check("throw", r[0]["throw_ft"], "13'-9\"")
check("no trim -> refuses, explains", r[1]["note"], "needs a trim height and a focus point")
check("unknown fixture -> refuses", r[2]["computed"], False)
check("unknown gel -> warns, does not guess", "open white" in r[3]["gel_warning"], True)
check("unknown gel -> open-white level", r[3]["footcandles"], 729)

print("\nwash")
w = client.post("/wash", json={"type": "S4 26", "throw": 14, "width": 24}).json()
check("field-to-beam spacing", w["spacing_ft"], "5'-4\"")
check("5 units cover 24 feet", w["row"]["count"], 5)
led = client.post("/wash", json={"type": "Lustr 26 EDLT", "throw": 14}).json()
check("LED penumbra is four inches", led["penumbra_ft"], "0'-4\"")
bad = client.post("/wash", json={"type": "SHEHDS 19", "throw": 14})
check("no beam figure -> 400, not a guess", bad.status_code, 400)

print("\nlens")
opts = client.get("/lens", params={"pool": 8, "throw": 17}).json()["options"]
check("26 deg is the closest to an 8ft pool", opts[0]["type"], "S4 26")

print("\nsaving a plot writes ONE file, and overwrites it")
# ⭐ Jerry, 2026.09.24: "the save is not automatically overwriting the file — it
# tries a new name Without Consent.plot (1).json." That bracket is a browser
# DOWNLOAD. The server writes the file now, so Save means the same thing in
# every browser — and pressing it twice has to leave one file, not two.
import os as _os
import tempfile as _tf
from plotedit import store as _ps

_os.environ["PLOTEDIT_PLOTS"] = _tf.mkdtemp()
_plot = {"formatVersion": 1, "show": "Save Test", "room": {"width": 10, "depth": 10},
         "positions": [], "instruments": []}

r1 = client.post("/save", json={"name": "Save Test.plot.json", "plot": _plot})
check("a save succeeds", r1.status_code, 200)
r2 = client.post("/save", json={"name": "Save Test.plot.json",
                                "plot": {**_plot, "show": "Save Test v2"}})
check("...and saving again succeeds", r2.status_code, 200)
check("...to the SAME path", r2.json()["path"], r1.json()["path"])
_files = _os.listdir(_ps.root())
check("...leaving exactly one file", len(_files), 1)
check("...with the SECOND save's content",
      client.get("/plots/Save Test.plot.json").json()["plot"]["show"], "Save Test v2")
check("...readable by more than its owner",
      oct(_os.stat(r1.json()["path"]).st_mode & 0o004), "0o4")

# 🔴 The name is a NAME. A page must not be able to write outside the folder.
for _bad in ["../escape.json", "/etc/passwd.json", "a/b.json", ".json",
             "notes.txt", "..\\win.json"]:
    _r = client.post("/save", json={"name": _bad, "plot": _plot})
    if _r.status_code != 400:
        FAILS.append(f"{_bad!r} was accepted as a plot name ({_r.status_code})")
check("every path that escapes the plots folder is refused",
      len(_os.listdir(_ps.root())), 1)

# 🔴 A SYMLINK inside the plots folder. This is the case the containment check
# exists for, and the name-pattern check cannot see it: "shared.json" is a
# perfectly good plot name, and if it happens to be a link into Dropbox — or
# anywhere else — following it writes outside the folder. Designers do symlink
# plots into a show folder, so this is an ordinary accident, not an attack.
_outside = _os.path.join(_tf.mkdtemp(), "someone-elses.json")
with open(_outside, "w") as _fh:
    _fh.write('{"keep": "me"}')
_os.symlink(_outside, _os.path.join(_ps.root(), "shared.json"))
_r = client.post("/save", json={"name": "shared.json", "plot": _plot})
check("a name that is a symlink out of the folder is refused", _r.status_code, 400)
with open(_outside) as _fh:
    check("...and the file it pointed at is untouched", _fh.read(), '{"keep": "me"}')

# ⚠ WINDOWS DEVICE NAMES. CON, NUL, LPT1 and friends are not filenames there —
# "CON.json" talks to the console and the extension is ignored — so a plot saved
# under one would silently not exist. Refused everywhere, so a plot written on a
# Mac cannot fail to open on Windows.
for _dev in ["CON.json", "nul.json", "com1.json", "LPT9.json", "aux.json"]:
    if client.post("/save", json={"name": _dev, "plot": _plot}).status_code != 400:
        FAILS.append(f"{_dev!r} was accepted — it is a device on Windows, not a file")
check("Windows device names are refused", True, True)
check("...but an ordinary name that starts the same is fine",
      client.post("/save", json={"name": "Concert.json", "plot": _plot}).status_code, 200)

# 🔴 A CORRUPT PLOT SAYS SO, AND NAMES ITSELF. json.JSONDecodeError is a
# subclass of ValueError, so an `except ValueError` above it swallowed every
# parse failure and the 422 branch was unreachable: the reply was 400 with a
# bare "Expecting value: line 1 column 1 (char 0)", which names neither the file
# nor what to do. pylint's bad-except-order found it in CI; no test did, because
# every test until now opened a file that parses.
with open(_os.path.join(_ps.root(), "broken.json"), "w") as _fh:
    _fh.write("{ not json at all ,,,")
_broken = client.get("/plots/broken.json")
check("a plot that will not parse is a 422", _broken.status_code, 422)
check("...and the message names the file", "broken.json" in _broken.json()["detail"], True)
check("...and it is still LISTED, not hidden",
      any(r["name"] == "broken.json" for r in client.get("/plots").json()["plots"]), True)
check("...saying it will not parse",
      next(r["show"] for r in client.get("/plots").json()["plots"]
           if r["name"] == "broken.json"), "— will not parse —")

check("a plot that is not there is a 404", client.get("/plots/nope.json").status_code, 404)
check("the listing names the folder", "folder" in client.get("/plots").json(), True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
