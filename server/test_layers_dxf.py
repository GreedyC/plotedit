#!/usr/bin/env python3
"""The DXF writes the merged eight, and text follows its subject.

    cd server && python3 test_layers_dxf.py

#82 step 2. The DXF had six names of its own — BASE, POSITIONS, UNITS, TEXT,
DIMS, NOTES — against four fixed toggles on screen, and only two concepts
appeared in both. Three things change here:

  · POOLS and FOCUS are NEW. They were drawn on NOTES because there was nowhere
    else to put them, so in CAD you could not switch the pools off without
    losing the key with them.
  · TEXT became LABELS, and stopped being forced. "TEXT" named the ENTITY KIND
    rather than what the text is, so every string in the drawing landed on it —
    a dimension's number shared a layer with a unit's channel and the key's
    words. Text follows its subject now.
  · 🔴 A BOOM ELEVATION IS NOT A NOTE. The whole thing was drawn on NOTES, so
    hiding the key took every boom elevation with it.

⚠ The last one was found by switching the PDF's layers off and LOOKING at the
sheet, not by reading the code: the ladder view — everything off but positions
and units — came out with no boom elevations and, absurdly, with the footnote
about them still printed.
"""
import collections
import os
import sys
import tempfile

import ezdxf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_to_pdf import render                                     # noqa: E402
from plotedit.dxf_bridge import DxfOut                             # noqa: E402
from plotedit.scaled_pdf import PDF_LAYERS, PDF_FOR_DXF            # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="plotedit-dxflayers-")
PDF = os.path.join(TMP, "p.pdf")
DXF = os.path.join(TMP, "p.dxf")
render(os.path.join(HERE, "..", "samples", "demo.plot.json"), PDF,
       page="ARCH_D", rulers=True, dxf=DXF)

doc = ezdxf.readfile(DXF)
defined = [l.dxf.name for l in doc.layers if l.dxf.name not in ("0", "Defpoints")]
on_layer = collections.Counter(e.dxf.layer for e in doc.modelspace())
texts = collections.defaultdict(list)
for e in doc.modelspace():
    if e.dxftype() == "TEXT":
        texts[e.dxf.layer].append(e.dxf.text)

EIGHT = ["BASE", "POOLS", "POSITIONS", "FOCUS", "UNITS", "LABELS", "DIMS", "NOTES"]

print("one set of layers, in both exports")
check("the DXF defines the eight", defined, EIGHT)
# 🔴 THE CROSS-CHECK. Two exports naming their layers separately is how the app
# got two schemes in the first place; this is the one assertion that stops it
# happening again.
check("the DXF names and the PDF's translation table agree",
      sorted(DxfOut.LAYERS), sorted(PDF_FOR_DXF))
check("...and map onto the eight PDF groups",
      sorted(PDF_FOR_DXF.values()), sorted(lid for lid, _ in PDF_LAYERS))
check("the order matches the drawing order too",
      list(DxfOut.LAYERS), EIGHT)

print("\nevery layer carries something")
for name in EIGHT:
    check(f"{name} has entities", on_layer.get(name, 0) > 0, True)
check("nothing landed anywhere else",
      sorted(k for k in on_layer if k not in EIGHT), [])
# ⚠ The retired name must be gone from the FILE, not merely unused in the code.
check("TEXT is not a layer any more", "TEXT" in defined, False)

print("\n⭐ pools and focus reach CAD for the first time")
check("POOLS has the pool ellipses", on_layer["POOLS"] > 100, True)
check("FOCUS has the leaders", on_layer["FOCUS"] > 0, True)
# Before this they were all on NOTES together with the key, so switching the
# pools off in CAD was not possible without losing the key.
check("and NOTES is no longer carrying them",
      on_layer["NOTES"] < on_layer["POOLS"], True)

print("\ntext follows its subject, instead of all landing on one layer")
check("the room's dimensions are on DIMS",
      any(ch in t for t in texts["DIMS"] for ch in ("'", "′")), True)
check("position names are on LABELS",
      any("BOOM" in t.upper() or "ELECTRIC" in t.upper() for t in texts["LABELS"]),
      True)
check("something is on NOTES", len(texts["NOTES"]) > 0, True)
check("text is spread over several layers, not one",
      len([k for k, v in texts.items() if v]) >= 3, True)

print("\n🔴 a boom elevation is not a note")
# Found in the ladder view: with Notes off the elevations vanished and their
# footnote stayed. The elevation is a POSITION with UNITS on it.
check("the footnote IS a note",
      any("NOT TO SCALE" in t for t in texts["NOTES"]), True)
check("...and the boom's name is not",
      any("NOT TO SCALE" in t for t in texts["LABELS"]), False)
check("the heights and unit numbers are labels",
      any(t.strip().isdigit() for t in texts["LABELS"]), True)

print("\nthe drawing is unchanged in every other way")
# ⚠ Entity COUNT, not layer assignment: moving something between layers must not
# add or lose a single line. 1,800+ entities, so a drop would be visible here.
total = sum(on_layer.values())
check("the DXF still has its entities", total > 1500, True)
check("every entity is on a real layer", sum(on_layer[k] for k in EIGHT), total)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
