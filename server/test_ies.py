#!/usr/bin/env python3
"""The IES parser, against Altman's real Spectra Cyc 100 measurement.

    cd server && python3 test_ies.py

Altman publish no photometric numbers in any datasheet for the Spectra Cyc range,
but they do publish IES files for the 100 and 200. This is how those become
usable — and the datasheet corroborates the parse exactly.
"""
import os
import sys

from plotedit.ies import read

HERE = os.path.dirname(os.path.abspath(__file__))
# ⭐ Test data lives WITH the test. This used to climb out of the repo into a
# folder on one laptop — so on CI the files were absent, the suite printed
# "skipped", exited 0, and reported success while testing nothing.
# verify_suites.py caught it on its first real run.
IES = os.path.join(HERE, "testdata", "ies")
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<50} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


path = os.path.join(IES, "SSCYC100-RGBA_2018-04-22.ies")
if not os.path.exists(path):
    # ⚠ A missing fixture is a FAILURE, not a skip. The file is committed
    # alongside this test, so its absence means something is broken — and a
    # suite that exits 0 when it cannot run is worse than one that is missing,
    # because it reports success.
    print(f"FAILED: no IES file at {path} — it should be committed beside this test")
    sys.exit(1)

p = read(path)
print("Altman Spectra Cyc 100 RGBA")
check("manufacturer", p["keywords"]["MANUFAC"], "ALTMAN")
check("lumens match the datasheet's 4,727", p["lumens"], 4727.0)
check("watts", p["watts"], 94.1)
check("max candela", round(p["max_candela"]), 4612)
check("Type C photometry", p["photometric_type"], "Type C")
check("46 vertical angles", len(p["vertical_angles"]), 46)
check("73 horizontal angles", len(p["horizontal_angles"]), 73)

print("\nit is asymmetric, and says so")
check("not symmetric", p["symmetric"], False)
check("strongly so", p["asymmetry"] > 0.5, True)
# A cyc light stands at the base of the cloth and throws UP it, so peak
# intensity is well off nadir. That is the fixture working as designed, not an
# error in the file.
check("peak 70° off nadir", p["peak_vertical_deg"], 70.0)

print("\nbad input is refused")
try:
    read("not an ies file\nat all\n")
    check("a non-IES file raises", "no error", "ValueError")
except ValueError:
    check("a non-IES file raises", "ValueError", "ValueError")

print()
print("an ellipsoidal is measured OUTWARD FROM THE AXIS, and still has angles")

# 🔴 THE BUG THIS EXISTS FOR. An ellipsoidal's sweep runs 0° to 90° — one side
# only — because the beam is symmetric about its axis. _angle_at walked outward
# in both directions, the low side immediately ran off the array, and every
# ellipsoidal IES ETC publish came back with field_angle None. The Altman cycs
# above hid it: an asymmetric unit is measured ACROSS its peak, so both edges
# exist. The reader had only ever been exercised on the one class it handled.
#
# Built here rather than shipped as another vendor file: a cone that falls to
# half at 10° and to a tenth at 15° must read as 20° beam and 30° field.
def _cone(halves, tenths, step=1.0, peak_at=0.0):
    """A synthetic symmetric distribution, measured from the axis outward."""
    vert = [i * step for i in range(int(90 / step) + 1)]
    vals = []
    for a in vert:
        d = abs(a - peak_at)
        if d <= halves:      v = 1.0 - 0.5 * (d / halves)
        elif d <= tenths:    v = 0.5 - 0.4 * ((d - halves) / (tenths - halves))
        else:                v = max(0.0, 0.1 - 0.1 * ((d - tenths) / 10))
        vals.append(round(v * 1000, 3))
    head = "IESNA:LM-63-2002\nTILT=NONE\n"
    body = (f"1 1000 1 {len(vert)} 1 1 2 0 0 0\n1 1 100\n"
            + " ".join(str(a) for a in vert) + "\n0\n"
            + " ".join(str(v) for v in vals) + "\n")
    return head + body

_p = read(_cone(10.0, 15.0))
check("a half-power edge at 10° reads as a 20° beam", _p["beam_angle"], 20.0)
check("a tenth-power edge at 15° reads as a 30° field", _p["field_angle"], 30.0)

# ⚠ AND THE SAMPLED PEAK LANDING OFF-AXIS MUST NOT CHANGE THE ANSWER. On a real
# symmetric beam the brightest cell falls on 0° or on the first step
# indifferently — the two are within measurement noise — and keying the rule off
# the PEAK rather than off the start of the sweep missed most of ETC's files.
# Here the cone is centred on the axis and a hair of noise lifts the second
# sample above the first, exactly as the real files do.
_noisy = _cone(10.0, 15.0)
_lines = _noisy.rsplit("\n", 2)
_vals = _lines[-2].split()
_vals[1] = str(float(_vals[0]) + 0.4)      # sample 1 now beats sample 0
_q = read("\n".join(_lines[:-2] + [" ".join(_vals), _lines[-1]]))
check("noise moving the sampled peak does not move the answer",
      _q["beam_angle"], 20.0)

# ⚠ WHAT IT CANNOT DO, said out loud: a genuinely tilted distribution measured
# from 0 is overstated by twice its offset, and nothing in a one-sided sweep can
# tell that apart from noise. It is the right trade for ellipsoidals, which are
# symmetric by construction — and the reason `symmetric` is reported separately
# so a caller can refuse to believe this on a unit that is not.
_tilted = read(_cone(10.0, 15.0, peak_at=1.0))
check("a truly off-axis cone is overstated, knowably", _tilted["beam_angle"], 22.0)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
