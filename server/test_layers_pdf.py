#!/usr/bin/env python3
"""The exported PDF has real layers, and switching one off removes real ink.

    cd server && python3 test_layers_pdf.py

#82 step 3. PDF has had optional content groups since 1.5 — a reader shows them
as a Layers panel with a checkbox each — and docs/LAYERS.md calls this the single
most valuable item on the list: an electrician on a ladder switches the rep plot
off in Acrobat and reads the pipes.

🔴 reportlab CANNOT MAKE THEM, so this is not a flag anybody switched on. Each
layer is drawn to its own reportlab canvas and PyMuPDF overlays them, one group
each. That is a lot of machinery to go wrong quietly, which is why the assertions
below are about INK rather than about structure: a group that exists, is named,
appears in the panel and hides nothing would pass every structural test and be
useless.

⚠ TWO TRAPS, both re-measured here rather than taken on trust from the plan:

  · `get_layers()` returns the reader's CONFIGURATIONS and comes back empty. The
    groups are in `get_ocgs()`.
  · `set_layer(-1, off=[…])` changes the stored state and NOT what renders.
    `set_layer_ui_config(n, action=2)` is the one that actually hides ink.

Both are easy to mistake for "it does not work", and one of them is easy to
mistake for "it works".
"""
import os
import sys
import tempfile

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_to_pdf import render                      # noqa: E402
from plotedit.scaled_pdf import PDF_LAYERS          # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "samples", "demo.plot.json")
TMP = tempfile.mkdtemp(prefix="plotedit-layertest-")


def build(name, **kw):
    out = os.path.join(TMP, name)
    render(DEMO, out, page="ARCH_D", **kw)
    return out


def names_of(doc):
    return [g["name"] for _, g in sorted(doc.get_ocgs().items())]


def ink(doc, dpi=50):
    """Dark pixels on page 1. The only question that matters."""
    px = doc[0].get_pixmap(dpi=dpi)
    s, n = px.samples, px.n
    return sum(1 for i in range(0, len(s), n) if s[i] < 200)


PDF = build("full.pdf", rulers=True)

print("the groups are in the file, named, in drawing order")
doc = pymupdf.open(PDF)
check("eight groups", len(doc.get_ocgs()), 8)
check("named and ordered", names_of(doc), [label for _, label in PDF_LAYERS])
# ⚠ The trap. This is not a bug and not an empty file — get_layers() reports
# the reader's configurations, of which there are none.
check("get_layers() is empty, which is NOT the answer", doc.get_layers(), [])

print("\n🔴 every layer removes ink that was really there")
ALL_ON = ink(doc)
removed = {}
for i, nm in enumerate(names_of(doc)):
    d = pymupdf.open(PDF)
    d.set_layer_ui_config(i, action=2)          # 2 = OFF
    removed[nm] = ALL_ON - ink(d)
    d.close()
for nm in names_of(doc):
    check(f"{nm} hides something", removed[nm] > 0, True)
# ⭐ And the sizes are sane rather than merely non-zero: the pipes and the key
# are the big ones on this plot, the focus leaders the smallest.
check("positions removes more than focus",
      removed["Positions"] > removed["Focus"], True)

print("\n⚠ the stored state is not the rendered state")
d = pymupdf.open(PDF)
d.set_layer(-1, off=[list(d.get_ocgs())[0]])
check("set_layer alone changes NOTHING on the page", ink(d), ALL_ON)
d.set_layer_ui_config(0, action=2)
check("set_layer_ui_config is the one that works", ink(d) < ALL_ON, True)

print("\n🔴 the title block is not a layer, and cannot be switched off")
d = pymupdf.open(PDF)
for i in range(len(names_of(d))):
    d.set_layer_ui_config(i, action=2)
frame_ink = ink(d)
check("with every layer off there is still ink", frame_ink > 0, True)
text = d[0].get_text()
check("...and it is the title block", "The Odd Couple" in text, True)
check("...with the scale", 'Scale 1/2" = 1\'-0"' in text, True)
# A sheet that can be stripped of what it is would be worse than no layers.
check("the drawing really did go", frame_ink < ALL_ON / 2, True)

print("\n⭐ the ladder view — everything off but positions and units")
d = pymupdf.open(PDF)
for i, nm in enumerate(names_of(d)):
    if nm not in ("Positions", "Units"):
        d.set_layer_ui_config(i, action=2)
left = d[0].get_text()
check("no position names survive", "HOUSE RIGHT BOOM" in left, False)
# 🔴 Found by rendering this view and LOOKING at it: two boom names were still
# on the sheet, because a boom is named in its own method and not through
# position_label(). Structure tests all passed while it was broken.
check("no boom names either", "BOOM" in left.upper().replace("THE ODD", ""), False)
check("the title block is still there", "The Odd Couple" in left, True)
check("there is still a drawing", ink(d) > frame_ink, True)

print("\npools and focus are separable, which they never were before")
# They are drawn on the DXF's NOTES layer because there was nowhere else to put
# them, so before this they could not be told apart from the key.
check("Pools is its own group", "Pools" in names_of(doc), True)
check("Focus is its own group", "Focus" in names_of(doc), True)
d = pymupdf.open(PDF)
idx = {nm: i for i, nm in enumerate(names_of(d))}
d.set_layer_ui_config(idx["Pools"], action=2)
only_pools_off = ink(d)
check("hiding Pools leaves Notes alone",
      only_pools_off > ALL_ON - removed["Pools"] - removed["Notes"], True)

print("\na layer with nothing on it gets no group at all")
# ⚠ What the designer hid is not drawn, so the group would be empty — and an
# empty row in the reader's Layers panel is a switch that does nothing.
bare = pymupdf.open(build("bare.pdf", show_pools=False, show_focus=False,
                          rulers=None))
check("no Pools group when the pools were not drawn",
      "Pools" in names_of(bare), False)
check("no Focus group either", "Focus" in names_of(bare), False)
# ⭐ Dimensions is STILL there without rulers, and that is correct — found by
# asserting the opposite and being wrong. The room's dimension STRINGS are drawn
# on every plot whether or not the rulers are asked for, and they live on DIMS.
# So the group is real, and hiding it hides the room's measurements.
check("Dimensions survives, because the room dimensions are always drawn",
      "Dimensions" in names_of(bare), True)
check("the ones that drew are still there",
      [n for n in ("Positions", "Units", "Notes") if n in names_of(bare)],
      ["Positions", "Units", "Notes"])

print("\nand the drawing itself is unchanged by being layered")
# 🔴 The whole point is that this is invisible to anyone who does not look for
# it. A layered sheet must carry the same ink as a flat one.
import plotedit.scaled_pdf as _sp                   # noqa: E402
_orig = _sp.Sheet.__init__


def _flat(self, *a, **kw):
    kw["layered"] = False
    return _orig(self, *a, **kw)


_sp.Sheet.__init__ = _flat
flat = build("flat.pdf", rulers=True)
_sp.Sheet.__init__ = _orig
fd = pymupdf.open(flat)
check("the flat sheet has no groups", len(fd.get_ocgs()), 0)
# Within a percent: the two are drawn by the same code, but a composited page
# resamples nothing — any difference here is a real difference in ink.
check("same ink as the layered sheet, within 1%",
      abs(ink(fd) - ALL_ON) <= max(1, ALL_ON // 100), True)
# ⚠ The same LINES, not the same string. A composited page holds its text in
# one XObject per layer, so extraction walks it in layer order rather than in
# drawing order — 176 lines either way, reordered. Comparing the raw strings
# fails for a reason that has nothing to do with what is on the paper.
_lines = lambda d: sorted(x.strip() for x in d[0].get_text().split("\n") if x.strip())
check("the same text, line for line", _lines(fd) == _lines(doc), True)
check("...and there is a useful amount of it", len(_lines(doc)) > 100, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
