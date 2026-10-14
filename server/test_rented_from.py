#!/usr/bin/env python3
"""Whose unit is it — the field the shop order is built from.

    cd server && python3 test_rented_from.py

#110. A plot said what was hung and where, and never whose it was, so the rental
order had to be re-derived every time by cross-referencing the plot against lists
of uncertain age — matching by TYPE, which cannot say WHICH four of six S4 26s
are the house's.

⭐ THE PRESENCE OF A NAME IS THE FACT (Jerry, 2026.10.14). `rentedFrom` holds who
it is hired from — "George", "Mary", a shop — and empty means not rented. No enum:
a plot routinely hires from two places at once, and the order groups by who.

🔴 SO FORGETTING TO FILL IT IN READS AS "THE HOUSE HAS IT", and the unit is not
ordered. That asymmetry is deliberate and is handled one level up, in the
`/rental` workflow: *"a unit assumed to be in the house, with no current list to
prove it, goes in the rental column with a note."* ⚠ The field stays truthful
about WHO rather than encoding a policy about what to assume — which is why there
is no "house" value to get wrong.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient            # noqa: E402
from plotedit import api, exports                    # noqa: E402

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = json.load(open(os.path.join(HERE, "..", "samples", "demo.plot.json"),
                      encoding="utf-8"))
client = TestClient(api.app)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def plot(rented):
    """units 1..n, each with the given rentedFrom (None leaves the key off)."""
    return {"formatVersion": 1, "show": "T", "room": {"width": 40, "depth": 40},
            "positions": [], "instruments": [
                {"unit": n, "type": "S4 26", "x": n, "y": 20, "channel": n,
                 **({} if r is None else {"rentedFrom": r})}
                for n, r in enumerate(rented, 1)]}


print("what counts as rented")
P = plot(["George", None, "", "   ", "Mary"])
check("a name is rented", api._is_rented(P["instruments"][0]), True)
check("absent is not", api._is_rented(P["instruments"][1]), False)
check("empty is not", api._is_rented(P["instruments"][2]), False)
# ⚠ Whitespace is not a name. A cell somebody tabbed through is not a hire.
check("whitespace is not", api._is_rented(P["instruments"][3]), False)
check("two renters on one plot",
      [i["unit"] for i in P["instruments"] if api._is_rented(i)], [1, 5])

print("\n⭐ the schedule carries it, which is the whole point")
sched = exports.schedule_csv(P)
check("there is a column for it", "Rented from" in sched.splitlines()[4], True)
check("...before Notes, after Accessory",
      sched.splitlines()[4].split(",")[-2:], ["Rented from", "Notes"])
rows = [r for r in sched.splitlines() if "George" in r or "Mary" in r]
check("both names reach it", len(rows), 2)
# ⚠ Blank for the rest. Most of a plot is the house's, so the column reads as a
# short list of exceptions rather than a wall of repeated words.
cells = [r.split(",")[-2] for r in sched.splitlines()[5:]
         if r.count(",") >= len(exports.SCHEDULE_COLUMNS) - 1]
check("every other cell is empty", [c for c in cells if c], ["George", "Mary"])
# 🔴 FOUND BY THIS TEST. The cell printed a whitespace-only value verbatim while
# api._is_rented treated it as NOT a hire — so a unit appeared in the schedule's
# rented column that the shop order correctly left out. Two places deciding the
# same thing differently is the fault this project keeps paying for.
check("...including the one that is only spaces", "   " in cells, False)

print("\n🔴 but the HOOKUP and the patch do not")
# The hookup is the board's document. Who owns a unit is not the board's problem.
check("no column on the hookup", "Rented" in exports.hookup_csv(P), False)
check("nothing in the patch", "rented" in exports.eos_patch_asc(P).lower()
      if hasattr(exports, "eos_patch_asc") else False, False)

print("\nthe drawing can hide them, and only the drawing")
check("nothing hidden changes nothing",
      [i["unit"] for i in api._hide_purposes(P, None, False)["instruments"]],
      [1, 2, 3, 4, 5])
check("hiding the hired units leaves the house's",
      [i["unit"] for i in api._hide_purposes(P, None, True)["instruments"]],
      [2, 3, 4])
# ⭐ One flag for all of them, whoever they are from — the drawing question is
# "what is arriving in a crate", not "whose crate".
check("George and Mary go together",
      [i["unit"] for i in api._hide_purposes(plot(["George", "Mary", None]),
                                             None, True)["instruments"]], [3])
# ⚠ And it composes with the purpose layers rather than fighting them.
both = plot(["George", None, None])
both["instruments"][1]["purpose"] = "back light"
check("purpose and rented hide together",
      [i["unit"] for i in api._hide_purposes(both, ["back light"], True)["instruments"]],
      [3])

print("\n🔴 the PLOT PDF honours it; the paperwork never does")
import pymupdf                                        # noqa: E402


def ink(resp):
    doc = pymupdf.Document(stream=resp.content, filetype="pdf")
    return sum(len(d["items"]) for d in doc[0].get_drawings())


hired = json.loads(json.dumps(DEMO))
for i in hired["instruments"][:6]:
    i["rentedFrom"] = "Production Advantage"
full = client.post("/export/pdf", json={"plot": hired, "page": "ARCH_D"})
less = client.post("/export/pdf", json={"plot": hired, "page": "ARCH_D",
                                        "hideRented": True})
check("both export", (full.status_code, less.status_code), (200, 200))
check("hiding six hired units removes real ink", ink(less) < ink(full), True)
# 🔴 THE HALF THAT WOULD ROT UNWATCHED. A shop order built from a drawing with
# the hired units switched off is an order for nothing.
for kind in ("schedule", "hookup", "magic-sheet", "eos"):
    a = client.post(f"/export/{kind}", json={"plot": hired})
    b = client.post(f"/export/{kind}", json={"plot": hired, "hideRented": True})
    check(f"/export/{kind} reports the whole rig either way",
          (a.status_code, a.content == b.content), (200, True))

print("\n⚠ and an older plot has none of this")
# A plot written before today has no rentedFrom anywhere. It must read as "the
# house has everything", draw unchanged, and schedule with an empty column.
check("the demo plot hires nothing",
      [i for i in DEMO["instruments"] if api._is_rented(i)], [])
check("...and is untouched by the filter",
      len(api._hide_purposes(DEMO, None, True)["instruments"]),
      len(DEMO["instruments"]))

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
