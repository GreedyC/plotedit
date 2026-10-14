#!/usr/bin/env python3
"""The lamps offered on a fixture are the lamps that fixture can be computed with.

    cd server && python3 test_lamp_list.py

🔴 WHAT THIS REPLACED, AND WHY. Until 2026.10.13 the browser kept a SECOND,
hand-typed copy of LAMP_MF's keys — one global list, offered on every barrel.
This file used to diff the two lists and it caught real drift twice: the three
Source 4WRD burners gained multipliers in v0.1.19 and never reached the dropdown,
and HPL 375 and HPL 550/77 had no multipliers at all until 2026.09.29.

⚠ BUT A LIST THAT IS MERELY IN STEP IS STILL WRONG, which the diff could never
see. Every lamp was offered on every fixture, so an Altman Shakespeare offered
HPL 750 — and picking it BLANKED THE FOOTCANDLES, because there is no HPL
multiplier for an Altman barrel and never will be. 194 of the 201 units in
Sample Big House are Shakespeares. The dropdown's only safe entry was the blank.

⭐ So the server now answers which lamps apply, per fixture, from the one table
that owns them (docs/LAMP-AND-MODE.md, acted on). The drift this file used to
guard against is now structurally impossible — and the first check below is that
nobody quietly reintroduces the second copy.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import photometrics as ph     # noqa: E402

MAIN_TS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "web", "src", "main.ts")
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("🔴 the browser keeps no copy of the lamp table")
src = open(MAIN_TS, encoding="utf-8").read()
# ⚠ The shape of the old bug: `lamps: ["HPL 750", …]` in the deps object. If it
# comes back, so does the drift, and so does a Shakespeare offering an HPL.
check("no `lamps:` array in main.ts",
      re.search(r"lamps\s*:\s*\[", src) is None, True)
check("it asks the server instead", "lampsFor:" in src, True)
# ⭐ And no lamp NAME is typed in the CODE either, which is how the array would
# come back one entry at a time. ⚠ Comments are stripped first and deliberately:
# the comment at the call site NAMES the bug this replaced — a Shakespeare being
# offered an HPL 750 — and that sentence is the reason the next person does not
# put the array back.
code = re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", src), flags=re.S)
typed = sorted(n for n in ph.LAMP_MF if n in code)
check("no lamp name is typed in main.ts's code", typed, [])
check("...though the comment still names the bug", "HPL 750" in src, True)

print("\n⭐ every lamp offered can actually be computed")
# 🔴 THE POINT OF THE WHOLE CHANGE. An offered lamp that yields no figure is a
# dropdown entry that promises light nobody measured.
bad_mult, bad_fc = [], []
for kind in ph.FIXTURES:
    for lamp in ph.lamps_for(kind):
        key, _, _ = ph.lookup(kind)
        if key not in ph.LAMP_MF.get(lamp, {}):
            bad_mult.append((kind, lamp))
        if ph.footcandles(kind, 25.0, lamp=lamp)[0] is None:
            bad_fc.append((kind, lamp))
check("...has a multiplier for that fixture", bad_mult, [])
check("...and returns a real footcandle figure", bad_fc, [])

print("\nthe reference lamp is offered first")
# The lamp the published chart was measured with is the one most plots want, and
# a dropdown is read top down.
wrong = [(k, ph.lamps_for(k)[0], ph.FIXTURES[k]["ref_lamp"])
         for k in ph.FIXTURES
         if ph.lamps_for(k) and ph.FIXTURES[k]["ref_lamp"] in ph.lamps_for(k)
         and ph.lamps_for(k)[0] != ph.FIXTURES[k]["ref_lamp"]]
check("...wherever it has a multiplier of its own", wrong, [])

print("\n🔴 the Shakespeare, which is what found this")
shake = [k for k in ph.FIXTURES if "Shakespeare" in k]
check("there are six of them", len(shake), 6)
# ⭐ One lamp this afternoon, five by the evening — Jerry produced the datasheet
# and #123 closed. The GLC is still first because it is the lamp the chart was
# measured with. test_shakespeare_lamps.py has the factors and the reasoning.
check("every barrel offers the same five",
      sorted({tuple(ph.lamps_for(k)) for k in shake}),
      [("GLC", "GKV", "HX604", "HX400", "HX401")])
check("...reference lamp first", {ph.lamps_for(k)[0] for k in shake}, {"GLC"})
# ⚠ Before the fix each of these was in the dropdown, and each blanked the figure.
offered_hpl = [k for k in shake if any("HPL" in l for l in ph.lamps_for(k))]
check("...and not one offers an HPL", offered_hpl, [])
check("an HPL in a Shakespeare still has no figure",
      ph.footcandles("Altman Shakespeare 30", 25.0, lamp="HPL 575")[0], None)
# ⭐ And it says WHY, rather than leaving an empty cell — photometrics.py's own
# scar: "a candela with no multiplier for the lamp actually in the fixture is a
# candela nobody can use".
check("...and says why",
      "no HPL 575 multiplier" in
      ph.footcandles("Altman Shakespeare 30", 25.0, lamp="HPL 575")[1], True)
# The blank is still right: with no lamp named, the chart's own lamp is used.
check("no lamp named uses the chart's lamp",
      round(ph.footcandles("Altman Shakespeare 30", 25.0)[0], 2),
      round(ph.footcandles("Altman Shakespeare 30", 25.0, lamp="GLC")[0], 2))

print("\n⚠ an empty list means two different things")
# One is "wrong question", the other is "nobody has published it", and they send
# a reader to different places — so the inspector must tell them apart.
check("a Lustr offers no lamp", ph.lamps_for("Lustr 26 EDLT"), [])
check("...because it has modes instead",
      len(ph.FIXTURES["Lustr 26 EDLT"].get("modes") or {}) > 0, True)
check("an S4 Zoom offers no lamp", ph.lamps_for("S4 Zoom 15-30 @23"), [])
check("...and has no modes either",
      len(ph.FIXTURES["S4 Zoom 15-30 @23"].get("modes") or {}), 0)
check("a type nobody knows offers none", ph.lamps_for("Strand Patt 23"), [])

print("\nand nothing in the table is unreachable")
# ⚠ A lamp with multipliers that no fixture offers is a lamp nobody can choose —
# the v0.1.19 bug in its new form, and the diff that used to catch it is gone.
reachable = {l for k in ph.FIXTURES for l in ph.lamps_for(k)}
check("every lamp in LAMP_MF is offered somewhere",
      sorted(set(ph.LAMP_MF) - reachable), [])
check("...and the HPL 575X asymmetry is real, not a loop bug",
      ("HPL 575X" in ph.lamps_for("S4 36"), "HPL 575X" in ph.lamps_for("S4 26")),
      (True, False))

print("\n⭐ and /fixtures carries it, because that is where the browser reads it")
from plotedit import api                   # noqa: E402  (slow import)
rows = api.fixtures()["fixtures"]
check("the payload has a lamps key", "lamps" in rows["S4 26"], True)
check("...matching lamps_for", rows["S4 26"]["lamps"], ph.lamps_for("S4 26"))
check("the Shakespeare's five are published",
      rows["Altman Shakespeare 30"]["lamps"],
      ["GLC", "GKV", "HX604", "HX400", "HX401"])
# ⚠ null, not [] — the browser reads `?? []`, and a JSON null is what an absent
# answer looks like everywhere else in this payload.
check("no lamps is null", rows["Lustr 26 EDLT"]["lamps"], None)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
