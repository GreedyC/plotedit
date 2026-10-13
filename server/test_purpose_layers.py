#!/usr/bin/env python3
"""Purpose layers: the drawing honours them, the paperwork never does.

    cd server && python3 test_purpose_layers.py

#108, the half that cost nothing. `purpose` is ALREADY a field on every
instrument and already the paperwork's word for "back light" or "front wash", so
the layers panel reads the purposes that are there rather than storing
membership a second time. ⭐ No change to the instrument record, nothing to
migrate, and no second copy of a fact to drift — which is the bug the eight
layers were created to fix in the first place.

🔴 THE LINE THIS SUITE EXISTS TO HOLD. Layer visibility is a property of the
DRAWING. The schedule, the hookup, the magic sheet, the patch and the loads
always report the WHOLE RIG — a load computed without the units somebody
switched off is the failure that trips a breaker on a Thursday. The plot PDF
honours the toggles because a designer who hides something to read the plan
expects the print to match; nothing else does, and the assertions below check
both halves of that, because only checking the first would let the second rot.

⚠ The bucketing is `magic_sheet_rows`', not this file's invention: blank or
missing is "unassigned". If the panel bucketed blanks differently, the drawing
and the magic sheet would disagree about what a group IS. Mirrored by
purposeOf() in web/src/layers.ts.
"""
import copy
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


def plot(purposes):
    return {"formatVersion": 1, "show": "T", "room": {"width": 40, "depth": 40},
            "positions": [], "instruments": [
                {"unit": n, "type": "S4 26", "x": n, "y": 20,
                 **({} if p is None else {"purpose": p})}
                for n, p in enumerate(purposes, 1)]}


def kept(p, hide):
    return [i.get("purpose") for i in
            api._hide_purposes(p, hide).get("instruments", [])]


print("what the filter keeps")
P = plot(["back light", "front wash", "back light", None, ""])
check("nothing hidden changes nothing", kept(P, None),
      ["back light", "front wash", "back light", None, ""])
check("an empty list changes nothing", kept(P, []),
      ["back light", "front wash", "back light", None, ""])
check("one purpose goes, and every unit carrying it",
      kept(P, ["back light"]), ["front wash", None, ""])
check("two at once", kept(P, ["back light", "front wash"]), [None, ""])
# ⚠ Missing and blank are ONE bucket, and it is the magic sheet's bucket.
check("'unassigned' takes the blanks AND the missing",
      kept(P, ["unassigned"]), ["back light", "front wash", "back light"])
check("a purpose nobody has is harmless", kept(P, ["nonsense"]),
      ["back light", "front wash", "back light", None, ""])
# ⭐ NOT case-folded, because magic_sheet_rows is not. Folding here would show
# one layer for two groups on the tech page — and showing both is the only thing
# that ever surfaces the typo.
check("case is not folded", kept(plot(["Area 1", "area 1"]), ["Area 1"]),
      ["area 1"])

print("\n⚠ and it is a COPY")
# Mutating the caller's plot would hide those units from whatever else the
# request went on to do with it.
before = copy.deepcopy(P)
api._hide_purposes(P, ["back light"])
check("the plot handed in is untouched", P, before)

print("\n⭐ the panel's buckets and the magic sheet's are the same buckets")
# 🔴 If these two ever part company, a designer switches off a group on the
# drawing and a DIFFERENT group disappears from the page read during tech.
rows = exports.magic_sheet_rows(plot(["back light", "front wash", None, ""]))
check("the magic sheet groups blanks as 'unassigned'",
      sorted(r["purpose"] for r in rows),
      ["back light", "front wash", "unassigned"])
check("...and the filter answers to the same name",
      kept(plot(["back light", None, ""]), ["unassigned"]), ["back light"])

print("\n🔴 the PLOT PDF honours it")
# ⚠ MEASURED IN INK, NOT IN BYTES. A PDF is not byte-deterministic — two
# identical requests differ, because reportlab stamps a creation time and new
# object ids into every file. A byte comparison here would have been a test that
# fails at random, and `len(content)` is a proxy for ink rather than ink.
import pymupdf                                      # noqa: E402


def ink(resp):
    """(vector items, text) actually on the page."""
    doc = pymupdf.Document(stream=resp.content, filetype="pdf")
    page = doc[0]
    return sum(len(d["items"]) for d in page.get_drawings()), page.get_text()


full = client.post("/export/pdf", json={"plot": DEMO, "page": "ARCH_D"})
some = client.post("/export/pdf", json={
    "plot": DEMO, "page": "ARCH_D",
    "hidePurposes": ["Area 1", "Area 2", "Area 3", "Area 4", "Area 5"]})
check("both export", (full.status_code, some.status_code), (200, 200))
full_ink, _ = ink(full)
some_ink, _ = ink(some)
# 🔴 A filter that ran and removed nothing would pass any assertion about the
# request going through, which is why this counts the marks on the paper.
check("hiding five purposes removes real ink", some_ink < full_ink, True)
check("...five units' worth of it", full_ink - some_ink > 50, True)
none_hidden = client.post("/export/pdf", json={
    "plot": DEMO, "page": "ARCH_D", "hidePurposes": []})
check("...and an empty list removes none", ink(none_hidden)[0], full_ink)

print("\n🔴 and NOTHING ELSE DOES — the half that would rot unwatched")
# A load computed without the units somebody switched off trips a breaker.
for kind in ("schedule", "hookup", "magic-sheet", "eos"):
    a = client.post(f"/export/{kind}", json={"plot": DEMO})
    b = client.post(f"/export/{kind}", json={"plot": DEMO,
                                             "hidePurposes": ["Area 1", "unassigned"]})
    check(f"/export/{kind} reports the whole rig either way",
          (a.status_code, a.content == b.content), (200, True))

print("\n⚠ the section is a drawing, but it is not the plan")
# The section draws ONE governing luminaire per position, chosen by geometry.
# It takes the sheet and the scale and none of the plan's layer options, so it
# is not wired to this and the request must not quietly half-apply it.
a = client.post("/export/section", json={"plot": DEMO, "page": "ARCH_D"})
b = client.post("/export/section", json={"plot": DEMO, "page": "ARCH_D",
                                         "hidePurposes": ["Area 1"]})
check("the section still exports", (a.status_code, b.status_code), (200, 200))
# ⚠ Hashed, so a failure says "different" in one line instead of printing a
# page of section text into the middle of the suite.
import hashlib                                      # noqa: E402
same = [hashlib.sha256(repr(ink(r)).encode()).hexdigest()[:12] for r in (a, b)]
check("...with exactly the same ink on it", same[0], same[1])

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
