#!/usr/bin/env python3
"""When a unit is drawn along its pipe instead of toward its focus. #113, #116.

    cd server && python3 test_two_point.py

Two reasons, one rule.

🔴 #113 — IT CANNOT TURN. A strip is bolted to the pipe at two points and tilts on
knobs at the mounting. Jerry, 2026.10.12: "mounted in two places and can only be
focused in one plane." Where it is aimed says nothing about which way its body
lies, and rotating it to the focus drew a six-foot batten standing on end across
the pipe it hangs from.

🔴 #116 — THERE IS NOTHING TO TURN TOWARD. A unit aimed within 2° of plumb has no
meaningful plan direction, and the one the arithmetic produces is floating-point
dust: a BILLIONTH of a foot sideways swings `pan` a quarter turn. Jerry hit it by
dragging a batten and putting it back.

⭐ And straight down is not a fault — it is the UNFOCUSED state, which is the
normal condition of a plot between the hang and the focus call.

⚠ THE SCREEN AND THE PAPER MUST AGREE. These helpers are mirrored in
web/src/render.ts, and this project has already shipped a bug where the same unit
pointed two ways on the two drawings.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import positions as P          # noqa: E402
from plotedit import symbols as S            # noqa: E402
from plotedit import photometrics as ph      # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<56} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("which fixtures are hung at two points")
for name, want in (("6ft strip PAR 38", True),
                   ("Chroma-Q Color Force II Plus 72", True),
                   ("Altman SSCYC100-RGBW", True),
                   ("ColorSource CYC", True),
                   ("S4 26", False),
                   ("PAR 64 MFL", False),
                   ("", False)):
    check(f"{name or '(blank)'}", S.is_two_point(name), want)

ACROSS = {"name": "ELECTRIC 3", "x1": -16, "y1": 8, "x2": 16, "y2": 8}
UPDOWN = {"name": "UP-DOWN", "x1": 0, "y1": 0, "x2": 0, "y2": 20}
BOOM = {"name": "BOOM SL", "x1": -18, "y1": 4, "x2": -18, "y2": 4, "type": "boom"}
POS = [ACROSS, UPDOWN, BOOM]

print("\n⭐ the pipe's own angle")
# ⭐ The unit FACES UPSTAGE (Jerry, 2026.10.12), so the pipe's run is turned by a
# half turn. A cross-stage electric gives 180, not 0 — which is what plotedit
# already drew, by way of a signed-zero accident, so no existing plot moves.
check("a cross-stage pipe faces upstage",
      P.position_angle({"position": "ELECTRIC 3"}, POS), 180.0)
check("an up-and-downstage pipe", P.position_angle({"position": "UP-DOWN"}, POS), 90.0)
# 🔴 THE SAME PIPE TYPED BACKWARDS MUST GIVE THE SAME ANSWER. Taking the facing
# from the run's direction flipped Big House's catwalks downstage while leaving
# its electrics upstage, because the catwalks were entered right to left.
REV = [{"name": "ELECTRIC 3", "x1": 16, "y1": 8, "x2": -16, "y2": 8}]
check("...and the same pipe entered backwards agrees",
      P.position_angle({"position": "ELECTRIC 3"}, REV), 180.0)
check("no position at all — across stage, upstage",
      P.position_angle({"position": ""}, POS), 180.0)
check("a position not in the plot", P.position_angle({"position": "GONE"}, POS), 180.0)
check("a position with no run", P.position_angle({"position": "BOOM SL"}, POS), 180.0)
check("UPSTAGE is the half turn", P.UPSTAGE, 180.0)

print("\n🔴 #113 — a strip takes the pipe angle whatever its elevation")
for el in (None, 5.0, 45.0, 89.0):
    check(f"strip at elevation {el}",
          P.takes_the_pipe_angle({"type": "6ft strip PAR 38"}, el), True)

print(f"\n🔴 #116 — and so does ANY unit within 2° of plumb (PLUMB_DEG = {P.PLUMB_DEG})")
check("an ERS focused normally keeps its aim",
      P.takes_the_pipe_angle({"type": "S4 26"}, 30.0), False)
check("...at 87.9°, still its aim", P.takes_the_pipe_angle({"type": "S4 26"}, 87.9), False)
check("...at 88.0°, the pipe", P.takes_the_pipe_angle({"type": "S4 26"}, 88.0), True)
check("...at 90°, the pipe", P.takes_the_pipe_angle({"type": "S4 26"}, 90.0), True)
# ⚠ An unfocused unit has no elevation at all. It must not be forced on a None.
check("no elevation computed — left alone",
      P.takes_the_pipe_angle({"type": "S4 26"}, None), False)

print("\n🔴 the dust that started it: a unit dragged and put back")
# At 25ft trim a billionth of a foot sideways swings pan a quarter turn. The
# elevation does not move at all, which is why the elevation is what we test.
base = ph.aim((0, 0, 25.0), (0, 0, 0.0))
for off in (1e-9, -1e-9, 0.001, -0.001):
    a = ph.aim((0, 0, 25.0), (off, 0, 0.0))
    moved_pan = abs(a["pan"] - base["pan"])
    moved_el = abs(a["elevation"] - base["elevation"])
    # ⭐ THE WHOLE BUG IN ONE ASSERTION: the aim barely moves, the pan leaps.
    check(f"offset {off:+}: elevation moves {moved_el:.4f}°", moved_el < 0.01, True)
    check(f"   ...while pan moves {moved_pan:.0f}°", moved_pan >= 90.0, True)
    check("   ...so the rule says pipe, not focus",
          P.takes_the_pipe_angle({"type": "S4 26"}, a["elevation"]), True)

print("\n⚠ the rule is mirrored in the browser, or the two drawings disagree")
ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "web", "src", "render.ts"), encoding="utf-8").read()
check("render.ts has positionAngle()", "export function positionAngle(" in ts, True)
check("...and takesThePipeAngle()", "export function takesThePipeAngle(" in ts, True)
check("...taking the perpendicular, not the run", "Math.atan2(ax + 0, -ay)" in ts, True)
check("...and killing negative zero the same way", "ax + 0" in ts, True)
check(f"...and the same {P.PLUMB_DEG}° threshold",
      f"PLUMB_DEG = {P.PLUMB_DEG}" in ts, True)
check("...and the same UPSTAGE half turn",
      f"UPSTAGE = {P.UPSTAGE}" in ts, True)

# 🔴 AND THE BROWSER SNAPS WHAT IT CHOSE, rather than overriding after the snap.
# This is the assertion that was missing. The Python had the ordering right and
# the TypeScript did not, so every suite passed while Big House's balcony rail —
# 37° off square — drew at its own rake on screen. Checking one side of a
# mirrored pair is not checking the pair.
check("the browser chooses the source BEFORE the snap",
      "const src = alongTheMount ?? (c?.pan ?? 0);" in ts, True)
check("...and snaps whatever it chose",
      "Math.round(src / 90) * 90" in ts, True)
check("🔴 and never overrides AFTER the snap",
      "alongTheMount ?? snapped" in ts, False)

print("\n🔴 the paper honours it too")
pdf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "plotedit", "scaled_pdf.py"), encoding="utf-8").read()
check("Sheet.unit takes a position_angle", "position_angle=None):" in pdf, True)
check("...and asks the shared rule", "_pos.takes_the_pipe_angle(" in pdf, True)
check("...choosing the source BEFORE the snap", "src = position_angle" in pdf, True)
check("...and snapping whatever it chose", "round(src / 90.0) * 90.0" in pdf, True)
plot_pdf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "plot_to_pdf.py"), encoding="utf-8").read()
check("...and plot_to_pdf passes it", "position_angle=_P.position_angle(" in plot_pdf, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
