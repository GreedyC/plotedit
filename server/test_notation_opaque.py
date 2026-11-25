#!/usr/bin/env python3
"""The §6.14.1 containers are OPAQUE, and the channel number is readable.

    cd server && python3 test_notation_opaque.py

🔴 WHY. The yoke is clamped to the pipe, so anything drawn off the back of a
unit sits on the batten whenever the two run parallel — and on a plot whose
positions form a grid, most units sit at a crossing. On Rev L of a real show the
batten ran dead through the middle of six channel circles and a hexagon. Jerry,
2026.11.02: "don't let any numbers be under the pipe — the circle holding the
channel number needs to be unbroken by the pipe, otherwise it's hard to read
sometimes."

⭐ THE FIX IS THE ONE THE FILE ALREADY USES FOR POSITION NAMES: knock the shape
out of what is underneath. `Sheet.text` has done it since issue #66, where 42
words on an imported venue plan had a line through them. A container is a
stronger case, because §6.14.1 gives the SHAPE the meaning — a hexagon with a
batten across it has stopped being a hexagon.

⚠ MOVING THE STACK INSTEAD DOES NOT WORK, and this is worth writing down so it
is not retried. Stepping the stack sideways off its own pipe is a few lines and
clears exactly one line: the unit then lands on the pipe CROSSING it. Measured
on the same sheet, that fixed one of the six.

⚠ AND THE RING HAD TO GROW WITH THE NUMBER. The circle is drawn in FEET and its
digits in POINTS, so the two scale apart: 0.52·size holds a 9pt number at
1/2" = 1'-0" and spills it at 1/4".

⚠ THE SCREEN AND THE PAPER MUST AGREE. web/src/render.ts draws the same
containers and has filled its circle white all along — which is why this showed
up only on paper. Its channel text is mirrored here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import symbols as S            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<58} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


class Rec:
    """A sheet that records the shapes asked for instead of drawing them."""

    def __init__(self, pt_per_ft=36.0):        # 36 pt/ft is 1/2" = 1'-0"
        self.pt_per_ft = pt_per_ft
        self.c = None                          # no canvas: _text_w falls back
        self.shapes = []
        self.texts = []

    def text(self, x, y, s, size=8, **k):
        self.texts.append((str(s), size))

    def circle(self, x, y, r, **k):
        self.shapes.append(("circle", r, k.get("fill")))

    def rect(self, x, y, w, h, **k):
        self.shapes.append(("rect", w, k.get("fill")))

    def polygon(self, pts, **k):
        self.shapes.append(("polygon", len(pts), k.get("fill")))

    def line(self, *a, **k):
        self.shapes.append(("line", None, None))


print("every container is opaque, so a batten cannot break its outline")
r = Rec()
S.notation(r, 0, 0, channel=12, circuit=34, dimmer=56,
           control="hard-and-soft-patch")
kinds = {k: fill for k, _, fill in r.shapes if k != "line"}
check("the channel circle is drawn", "circle" in kinds, True)
check("...and it is filled", kinds.get("circle") is not None, True)
check("the circuit hexagon is a polygon, not six loose lines",
      "polygon" in kinds, True)
check("...and it is filled", kinds.get("polygon") is not None, True)
check("the dimmer rectangle is drawn", "rect" in kinds, True)
check("...and it is filled", kinds.get("rect") is not None, True)

# 🔴 The hexagon used to be six `line` calls, which cannot be filled at all.
# If it goes back to that, the fill above silently stops existing.
check("no bare lines are left in the stack",
      sum(1 for k, _, _ in r.shapes if k == "line"), 0)

print()
print("the channel number is the size Jerry asked for")
check("CHANNEL_PT", S.CHANNEL_PT, 9)
sizes = dict(r.texts)
check("the channel is drawn at CHANNEL_PT", sizes.get("12"), S.CHANNEL_PT)
check("...and it is bigger than the circuit beside it",
      sizes.get("12") > sizes.get("34"), True)

print()
print("the ring holds its own digits at any scale")
SIZE = 0.42
base = SIZE * 0.52
check("at 1/2\" a two-digit channel needs no more room than §6.14.1 gives it",
      round(S.channel_radius(Rec(36.0), 12, SIZE), 4), round(base, 4))
# ⚠ At 1/4" the ring is half the points across and the number is unchanged.
quarter = S.channel_radius(Rec(18.0), 12, SIZE)
check("at 1/4\" the ring grows rather than letting the number hang out",
      quarter > base, True)
check("a three-digit channel needs more ring than a one-digit one",
      S.channel_radius(Rec(18.0), 456, SIZE) > S.channel_radius(Rec(18.0), 4, SIZE),
      True)
check("it never SHRINKS the ring", S.channel_radius(Rec(400.0), 1, SIZE) >= base, True)
check("no canvas and no scale falls back to the plate figure",
      S.channel_radius(Rec(None), 12, SIZE), base)

print()
print("the screen is mirrored, so the two drawings still agree")
render = open(os.path.join(HERE, "..", "web", "src", "render.ts"),
              encoding="utf-8").read()
check("render.ts sizes the channel from a named constant",
      "const CH = TEXT * 0.9" in render, True)
check("...and grows its circle to hold it", "Math.max(0.55," in render, True)
check("...and still fills it", 'fill: "#fff"' in render, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
