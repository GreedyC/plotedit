#!/usr/bin/env python3
"""A striplight is hung at two points and does not turn. #113.

    cd server && python3 test_two_point.py

🔴 Jerry, 2026.10.12: "A strip light is mounted in two places and can only be
focused in one plane." Every other symbol hangs on one yoke and is drawn rotated
to face its focus point. A strip is bolted along the pipe, so its body lies where
it is HUNG. Rotating it to the focus drew a six-foot unit lying diagonally across
the stage, where nobody could hang it.

⚠ THE SCREEN AND THE PAPER MUST AGREE. `positions.mount_angle()` is mirrored by
`mountAngle()` in web/src/render.ts, and this project has already shipped a bug
where the same unit pointed two ways on the two drawings.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import positions as P          # noqa: E402
from plotedit import symbols as S            # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("which fixtures are hung at two points")
for name, want in (("6ft strip PAR 38", True),
                   ("Chroma-Q Color Force II Plus 72", True),
                   ("Chroma-Q Color Force II Plus 72 Cyc", True),
                   ("Altman SSCYC100-RGBW", True),
                   ("ColorSource CYC", True),
                   ("S4 26", False),
                   ("Lustr 2 26", False),
                   ("PAR 64 MFL", False),
                   ("", False)):
    check(f"{name or '(blank)'}", S.is_two_point(name), want)

ACROSS = {"name": "ELECTRIC 3", "x1": -16, "y1": 8, "x2": 16, "y2": 8}
UPDOWN = {"name": "UP-DOWN", "x1": 0, "y1": 0, "x2": 0, "y2": 20}
BOOM = {"name": "BOOM SL", "x1": -18, "y1": 4, "x2": -18, "y2": 4, "type": "boom"}
POS = [ACROSS, UPDOWN, BOOM]
strip = lambda p: {"type": "6ft strip PAR 38", "position": p}   # noqa: E731

print("\n⭐ the angle comes from the PIPE, not the focus")
check("a unit that CAN pan is left alone",
      P.mount_angle({"type": "S4 26", "position": "ELECTRIC 3"}, POS), None)
check("a strip on a cross-stage pipe lies across stage",
      P.mount_angle(strip("ELECTRIC 3"), POS), 0.0)
check("a strip on an up-and-downstage pipe lies up and down",
      P.mount_angle(strip("UP-DOWN"), POS), 90.0)

print("\n🔴 and the focus point cannot move it")
# The whole bug: these three differ only in where they are aimed.
for aim in ((-20.0, 2.0), (20.0, 2.0), (0.0, 30.0)):
    inst = dict(strip("ELECTRIC 3"), focusX=aim[0], focusY=aim[1], x=0, y=8, trim=14)
    check(f"aimed at {aim} — still across stage", P.mount_angle(inst, POS), 0.0)

print("\n⚠ no pipe to read, so a documented default")
# A ground row stands on the deck and may belong to no position at all. Across
# stage is where ground rows go — a limitation, not a measurement.
check("no position at all", P.mount_angle(strip(""), POS), 0.0)
check("a position that does not exist", P.mount_angle(strip("GONE"), POS), 0.0)
check("a position with no run (both ends the same)",
      P.mount_angle(strip("BOOM SL"), POS), 0.0)

print("\n⚠ the rule is mirrored in the browser, or the two drawings disagree")
ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "web", "src", "render.ts"), encoding="utf-8").read()
check("render.ts has mountAngle()", "export function mountAngle(" in ts, True)
check("...and it reads the position's run", "pos.x2 - pos.x1" in ts, True)
check("...and uses the same atan2(dy, dx)", "Math.atan2(dy, dx)" in ts, True)
check("...and the pan is overridden, not the photometrics",
      "const pan = alongTheMount ?? snapped;" in ts, True)

print("\n🔴 the paper honours it too")
pdf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "plotedit", "scaled_pdf.py"), encoding="utf-8").read()
check("Sheet.unit takes a mount_angle", "mount_angle=None):" in pdf, True)
check("...and it overrides the drawn angle only",
      "draw_deg = mount_angle" in pdf, True)
plot_pdf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "plot_to_pdf.py"), encoding="utf-8").read()
check("...and plot_to_pdf passes it", "mount_angle=_P.mount_angle(" in plot_pdf, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
