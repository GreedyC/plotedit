#!/usr/bin/env python3
"""The resolver, against the names that are actually in Jerry's archive.

    cd server && python3 test_names.py

Before this existed, NONE of the 38 distinct instrument names in the archive
matched a photometric table key — an imported plot drew correctly and was
silently unlit.
"""
import sys

from plotedit import fixture_names as fn
from plotedit import photometrics as ph

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("names from the archive resolve to table keys")
for raw, want in [
    ("ETC Source4 36deg", "S4 36"),
    ("ETC Source4 26deg", "S4 26"),
    ("ETC Source4 19deg", "S4 19"),
    ("ETC Source4 50deg", "S4 50"),
    ("ETC CE Source4 26deg", "S4 26"),          # CE units, same optics
    ("S4-50°", "S4 50"),
    ("S4-50Â°", "S4 50"),                        # mojibake from an old export
    ("ETC CE Source4 PAR MCM (MFL)", "S4 EA PAR MFL"),
    ("ETC Source4 PARNel", "S4 PARNel @25"),
    ("S4 26", "S4 26"),                          # a key resolves to itself
]:
    check(f"{raw!r}", fn.resolve(raw, ph.FIXTURES)[0], want)

print("\nColorSource — datasheets fetched 2026.09.23")
for raw, want in [
    ("S4-26° LED-ClrSrc", "ColorSource Spot 26 EDLT"),
    ("S4-36° LED-ClrSrc", "ColorSource Spot 36 EDLT"),
    ("ETC ColorSource CYC", "ColorSource CYC"),
]:
    check(f"{raw!r}", fn.resolve(raw, ph.FIXTURES)[0], want)
check("a ColorSource Spot computes a level",
      round(ph.footcandles("S4-26° LED-ClrSrc", 14, mode="At 3200K")[0]), 240)
# The CYC is asymmetrical: ETC publishes NO beam angle and NO candela, so it must
# resolve to the fixture and then say why there is no number — not look unknown.
_key, _row, _ = ph.lookup("ETC ColorSource CYC")
check("the CYC resolves", _key, "ColorSource CYC")
check("...but has no beam angle, by design", _row["field"], None)
check("...and says so", "asymmetrical" in _row["source"], True)

print("\nSource Four LED — Jerry confirmed these were Lustrs (Wizard of Oz, 2022)")
check("'ETC Source4 LED 26deg'", fn.resolve("ETC Source4 LED 26deg", ph.FIXTURES)[0],
      "Lustr 26 EDLT")
check("...and computes a level",
      round(ph.footcandles("ETC Source4 LED 26deg", 14, mode="Regulated 3200K")[0]), 273)

print("\ncyc units — asymmetric, so no beam angle exists to publish")
for raw, key in [("ETC ColorSource CYC", "ColorSource CYC"),
                 ("Altman Spectra Cyc 50", "Altman Spectra Cyc 50")]:
    k, row, _ = ph.lookup(raw)
    check(f"{raw!r} resolves", k, key)
    check("   ...with no beam angle", row["field"], None)
    check("   ...and the note says why", any(w in row["source"].lower()
          for w in ("asymmetric", "no photometrics")), True)
# Altman publishes nothing at all for the 50 — their own spec says the IES file
# is available on request. Where to GET real figures belongs in the note.
_, _row, _ = ph.lookup("Altman Spectra Cyc 50")
check("Altman note names the way to get real figures",
      "IES" in _row["source"], True)
check("...and the 4-foot centers, which change a plot", _row["spacing_ft"], 4.0)
check("the 50 still has no candela", _row["cd"], None)
check("...and points at the 100, which does", "100" in _row["source"], True)

print("\nAltman Spectra Cyc — the 100 has a real goniometric measurement")
k, row, _ = ph.lookup("Spectra Cyc 100")
check("resolves to the RGBA", k, "Altman Spectra Cyc 100 RGBA")
check("candela from the IES file", row["cd"], 4612)
check("lumens match the datasheet", row["lumens"], 4727)
check("marked asymmetric", row["asymmetric"], True)
check("peak is 70° off nadir — it throws UP a cyc", row["peak_vertical_deg"], 70.0)
check("and a level can be computed",
      round(ph.footcandles("Spectra Cyc 100", 14)[0]), 24)

print("\na CORRECTION overrides the paperwork, and says so out loud")
# Jerry's Wizard of Oz rows read "Altman Spectra CYC 50". He confirmed
# 2026.09.23 they were 100s. Lightwright's load comes from the library entry for
# the typed name, so the name and the 50w are ONE fact, not two — which is why a
# designer's memory can outrank a spreadsheet here.
k, note = fn.resolve("Altman Spectra CYC 50")
check("the paperwork name now resolves to the 100", k, "Altman Spectra Cyc 100 RGBA")
check("the note leads with 'corrected'", note.startswith("corrected:"), True)
check("...and dates the decision", "2026.09.23" in note, True)
check("...and flags the RGBA/RGBW assumption", "RGBW" in note, True)
# The real 50 must stay reachable. A correction is about ONE show's paperwork,
# not a claim that the fixture does not exist.
k50, _ = fn.resolve("Altman Spectra Cyc 50")
check("the exact key still reaches the real 50", k50, "Altman Spectra Cyc 50")
check("a level can now be computed for the Oz cycs",
      round(ph.footcandles("Altman Spectra CYC 50", 14)[0]), 24)

print("\nreal fixtures with no data give a REASON, not silence")
# ⭐ "Altman 6in Fres" used to be in this list, as "no datasheet fetched". Jerry
# produced the 65Q datasheet on 2026.10.13 and it now resolves — see
# test_fresnel.py. The 8" has not been found, so it takes its place here, and
# the HPL-socket 65Q joins it: Altman publish a chart for the BTN lamp and NO
# correction factor for the HPL rows, so that variant's output is genuinely not
# on file. ⚠ A fixture leaving this list is the good outcome; a fixture being
# ALIASED off it without data would be the bad one.
for raw, fragment in [
    ("Altman 8in Fresnel", "no datasheet"),
    ("Altman 65Q-HPL", "no correction factor"),
    ("Blizzard Lighting AtmosFEAR Tour HZ", "not a luminaire"),
    ("ETC Source4 Jr Zoom", "different fixture"),
]:
    key, note = fn.resolve(raw, ph.FIXTURES)
    check(f"{raw!r} -> no key", key, None)
    check(f"   ...and says why", fragment.lower() in note.lower(), True)

print("\nnonsense and blanks")
check("unknown name", fn.resolve("Nonsense 12", ph.FIXTURES)[0], None)
check("empty", fn.resolve("", ph.FIXTURES)[0], None)
check("a system name, not a fixture", fn.resolve("CYC", ph.FIXTURES)[0], None)

print("\nthe paperwork name computes the SAME as the table key")
for raw, key in [("ETC Source4 26deg", "S4 26"), ("S4-50°", "S4 50"),
                 ("ETC CE Source4 19deg", "S4 19")]:
    a = ph.footcandles(raw, 14, lamp="HPL 575")[0]
    b = ph.footcandles(key, 14, lamp="HPL 575")[0]
    check(f"{raw!r} == {key!r}", round(a), round(b))
    pa, pb = ph.pool(raw, 14)["field"], ph.pool(key, 14)["field"]
    check(f"   ...and the pool matches", round(pa, 4), round(pb, 4))

print("\nthe note says how a name was read")
_, note = ph.footcandles("ETC Source4 26deg", 14, lamp="HPL 575")
check("footcandle note carries the translation", "read as 'S4 26'" in note, True)

print("\nand the symbol is the same too")
from plotedit import symbols as sym
check("ColorSource draws five dots, per 6.16",
      sum(1 for p in sym.for_type("S4-26° LED-ClrSrc") if p[0] == "circle"), 5)
check("a Lustr draws seven",
      sum(1 for p in sym.for_type("Lustr 26 EDLT") if p[0] == "circle"), 7)
check("'ETC Source4 19deg' draws what 'S4 19' draws",
      [p[0] for p in sym.for_type("ETC Source4 19deg")],
      [p[0] for p in sym.for_type("S4 19")])

print("\nAltman Shakespeare — a house rep plot, 2026.10.09")
check("'Altman S6-30' is a Shakespeare 30, not a Source Four",
      fn.resolve("Altman S6-30", ph.FIXTURES)[0], "Altman Shakespeare 30")
check("'Shakespeare 10°' resolves", fn.resolve("Shakespeare 10°", ph.FIXTURES)[0], "Altman Shakespeare 10")
_len = lambda k: round(max(a for p in sym.for_type(k) if p[0] == "poly" for a, _c in p[1])
                       - min(a for p in sym.for_type(k) if p[0] == "poly" for a, _c in p[1]), 3)
check("a Shakespeare 30 is drawn at its own length, 25 1/8\"", _len("Altman Shakespeare 30"),
      round(25.125 / 12, 3))
check("the 10° barrel is longer than the 30°",
      _len("Altman Shakespeare 10") > _len("Altman Shakespeare 30"), True)
check("a 30° carries RP-2's 26-30° diagonal",
      [p[0] for p in sym.for_type("Altman Shakespeare 30")][1:], ["line"])

print("\nthe 2025 USITT RP's 14° mark")
_m14 = [p for p in sym.for_type("S4 14") if p[0] == "line"]
check("a 14° carries three lines", len(_m14), 3)
check("...parallel to the beam (each line is level in the symbol frame)",
      all(abs(p[1][1] - p[2][1]) < 1e-9 for p in _m14), True)
check("a 10° is unchanged: no mark", [p[0] for p in sym.for_type("S4 10")][1:], [])

print("\nthe beam angle written in the barrel (2025 RP)")
_txt = lambda k, **kw: [p[2] for p in sym.for_type(k, **kw) if p[0] == "text"]
check("a Shakespeare 40 writes 40", _txt("Altman Shakespeare 40", angle_in_barrel=True), ["40"])
check("...and a 10° writes 10 — the two that both carried no mark",
      _txt("Altman Shakespeare 10", angle_in_barrel=True), ["10"])
check("the number REPLACES the mark: a 26° loses its diagonal",
      [p[0] for p in sym.for_type("S4 26", angle_in_barrel=True)], ["poly", "text"])
check("...and sits in the lens housing, ahead of the unit number in the body",
      [p[1][0] < -0.4 for p in sym.for_type("S4 26", angle_in_barrel=True) if p[0] == "text"],
      [True])
check("off by default: the marks are unchanged", _txt("S4 26"), [])
check("a zoom keeps its Z, not the one angle in its name",
      _txt("S4 Zoom 25-50", angle_in_barrel=True), ["Z"])
check("a PAR is not an ellipsoidal and ignores it", _txt("PAR64 MFL", angle_in_barrel=True), [])

print("\nChroma-Q Color Force II Plus 72 — the 2025 RP's LED batten")
check("'Color Force II Plus 72' resolves",
      fn.resolve("Color Force II Plus 72", ph.FIXTURES)[0], "Chroma-Q Color Force II Plus 72")
check("...its cyc lens is its own row", fn.resolve("Color Force II Plus 72 Cyc", ph.FIXTURES)[0],
      "Chroma-Q Color Force II Plus 72 Cyc")
check("the plain Color Force II 72 does NOT borrow the Plus figures",
      fn.resolve("Color Force II 72", ph.FIXTURES)[0] == "Chroma-Q Color Force II Plus 72", False)
_b = sym.for_type("Chroma-Q Color Force II Plus 72")
_poly = [q for q in _b if q[0] == "poly"][0][1]
check("drawn at its real length, 69 1/4\"",
      round(max(c for _a, c in _poly) - min(c for _a, c in _poly), 3), round(69.25 / 12, 3))
check("...and its real depth, 6 1/2\"",
      round(max(a for a, _c in _poly) - min(a for a, _c in _poly), 3), round(6.5 / 12, 3))
_dots = [q for q in _b if q[0] == "circle"]
check("four dots for RGBA", len(_dots), 4)
check("...all in one end", all(q[1][1] < -2.5 for q in _dots), True)
check("the cyc LENS is still a batten, not a cyc cell",
      [q[0] for q in sym.for_type("Chroma-Q Color Force II Plus 72 Cyc")],
      [q[0] for q in _b])
check("measured: 92,600 cd standard, 32,000 with the cyc lens",
      (ph.FIXTURES["Chroma-Q Color Force II Plus 72"]["cd"],
       ph.FIXTURES["Chroma-Q Color Force II Plus 72 Cyc"]["cd"]), (92600, 32000))

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
