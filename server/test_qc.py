#!/usr/bin/env python3
"""The QC pass finds what a person would find by reading the plot carefully.

    cd server && python3 test_qc.py

⭐ WHAT THIS IS GUARDING. Every defect in the sample plots so far was found by
LOOKING at a drawing — the raked catwalk units, the batten dragged and put back,
the gel punctuation that silently removed every footcandle in the show. A plot is
two hundred near-identical records and the eye slides off it, so the useful test
is not "does the checker run" but "does each check fire on the thing it names,
and stay quiet on the thing it does not".

🔴 THE HALF THAT MATTERS IS THE QUIET HALF. A checker that flags good data gets
switched off within a week, so every check here is tested twice: once on a plot
that has the defect, once on one that does not. demo.plot.json is the second
test — it focuses two units at 3'-6" and one at 1'-6", which are a mid and a
shin, and a checker with an opinion about head height would call all three wrong.

🔴 BOTH SHIPPED SAMPLES ARE NOW ASSERTED FREE OF ERRORS, and that assertion is
the point of the file. They were not when the pass was written: Big House had
three duplicate units and `focusH: 0` on all 201 instruments, so every pool and
footcandle in it computed at the floor. Fixed 2026.10.13 (#125). This is what
stops it coming back — a sample plot is the first thing a stranger opens, and the
only thing that keeps it honest is a check that runs every time.

⚠ Warnings are NOT asserted away. Big House still reports three, all of them
true and all of them documented: the units are focused straight down as a
stand-in, 64 are unpatched, and eight are coloured "NC/Temp", which is a note to
the electrician rather than a filter.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import positions, qc         # noqa: E402

FAILS = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<56} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def plot(instruments, positions=None):
    """A minimal plot. The defaults are deliberately CLEAN, so each test below
    introduces exactly one defect and nothing else can account for a finding."""
    return {"positions": positions if positions is not None else
            [{"name": "#1 ELECTRIC", "type": "electric",
              "x1": 0, "y1": 20, "x2": 40, "y2": 20, "trim": 20}],
            "instruments": instruments}


def unit(n, x, **kw):
    """One clean unit on #1 ELECTRIC: on the run, at its position's trim,
    focused somewhere real at head height, with a channel and a known type."""
    rec = {"unit": n, "channel": n, "type": "S4 26", "position": "#1 ELECTRIC",
           "x": x, "y": 20, "trim": 20,
           "focusX": x, "focusY": 10, "focusH": 5.5, "color": "R33"}
    rec.update(kw)
    return rec


def slugs(findings, level=None):
    return sorted(f.check for f in findings
                  if level is None or f.level == level)


CLEAN = plot([unit(1, 5), unit(2, 15), unit(3, 25)])

print("a clean plot says nothing at all")
# ⚠ If this ever reports anything, every other test below is meaningless — the
# finding could be coming from the fixture rather than from the defect.
check("no findings", qc.check(CLEAN), [])
check("...and the report says so", "nothing to report" in qc.report([]), True)

print("\n🔴 errors — the file contradicts itself")

two_nines = plot([unit(9, 5), unit(9, 15), unit(10, 25)])
check("two units 9 on one pipe", slugs(qc.duplicate_units(two_nines)),
      ["duplicate-unit"])
check("...and it is an error", qc.duplicate_units(two_nines)[0].level, "error")
check("...naming both by channel and place",
      len(qc.duplicate_units(two_nines)[0].units), 2)
# ⭐ The same unit number on a DIFFERENT position is correct and ordinary: every
# pipe in the house has a unit 1.
elsewhere = plot([unit(1, 5), unit(1, 5, position="#2 ELECTRIC")],
                 positions=[{"name": "#1 ELECTRIC", "x1": 0, "y1": 20,
                             "x2": 40, "y2": 20, "trim": 20},
                            {"name": "#2 ELECTRIC", "x1": 0, "y1": 20,
                             "x2": 40, "y2": 20, "trim": 20}])
check("unit 1 on two different pipes is fine", qc.duplicate_units(elsewhere), [])

orphan = plot([unit(1, 5, position="#9 ELECTRIC")])
check("a position the plot does not have", slugs(qc.unknown_positions(orphan)),
      ["unknown-position"])
check("...is an error", qc.unknown_positions(orphan)[0].level, "error")
check("...and the name is quoted so it can be searched for",
      "'#9 ELECTRIC'" in qc.unknown_positions(orphan)[0].says, True)
# ⚠ Case and stray spaces are not a defect. A position typed "#1 Electric" in
# the schedule and "#1 ELECTRIC" on the pipe is the same pipe.
check("case and spacing do not count",
      qc.unknown_positions(plot([unit(1, 5, position=" #1 electric ")])), [])

off = plot([unit(1, 5, y=24)])             # 4 feet upstage of its own electric
check("a unit off its pipe", slugs(qc.off_the_run(off)), ["off-the-run"])
check("...is an error", qc.off_the_run(off)[0].level, "error")
check("...and says how far", "4'-0\"" in qc.off_the_run(off)[0].units[0], True)
# ⭐ Six inches of slack, because a unit is a body on a pipe and not a point.
check("4 inches off is not off", qc.off_the_run(plot([unit(1, 5, y=20.33)])), [])
# ⚠ A BOOM is a single point in plan and its units are drawn to the side
# (RP-2 §6.12), so distance is measured to the position, which is that point.
boom = plot([unit(1, 30, y=14, position="SR Boom", height=5)],
            positions=[{"name": "SR Boom", "type": "boom", "x1": 30, "y1": 14,
                        "x2": 30, "y2": 14, "trim": 20}])
check("a boom unit is on its boom", qc.off_the_run(boom), [])

check("a type the table has never heard of",
      slugs(qc.unknown_types(plot([unit(1, 5, type="Strand Patt 23")]))),
      ["unknown-type"])
# ⭐ An alias is not an error. "ETC S4 26" IS "S4 26".
check("an alias resolves quietly",
      qc.unknown_types(plot([unit(1, 5, type="ETC S4 26")])), [])
# 🔴 FOUND WRITING THIS TEST, and left failing-as-documented rather than fixed
# here: the manufacturer's own full spelling does NOT resolve. "Source 4 26" and
# "ETC S4 26" both do. See docs/NEXT.md — it belongs in the alias table, not in
# a QC suite.
check("⚠ 'ETC Source Four 26' does not resolve — see NEXT.md",
      bool(qc.unknown_types(plot([unit(1, 5, type="ETC Source Four 26")]))), True)

print("\n⚠ warnings — something a designer might mean")

deck = plot([unit(1, 5, focusH=0)])
check("focus height 0", slugs(qc.focus_heights(deck)), ["focus-at-the-deck"])
check("...is a WARNING, not an error", qc.focus_heights(deck)[0].level, "warning")
# 🔴 THE WHOLE POINT OF THAT CHECK. Blank is head height; zero is the floor and
# travels as the floor. On a 30' electric that is a 30' throw where the truth is
# 24'-6", and every pool and every footcandle on every sheet is wrong.
blank = plot([unit(1, 5)])
blank["instruments"][0].pop("focusH")
check("blank focus height is head height, not a finding", qc.focus_heights(blank), [])
# ⭐ demo.plot.json's side light is the reason the range is wide.
check("a shin at 1'-6\" is not a finding", qc.focus_heights(plot([unit(1, 5, focusH=1.5)])), [])
check("a mid at 3'-6\" is not a finding", qc.focus_heights(plot([unit(1, 5, focusH=3.5)])), [])
check("55 feet is", slugs(qc.focus_heights(plot([unit(1, 5, focusH=55)]))),
      ["focus-height-unusual"])

plumb = plot([unit(1, 5, focusX=5, focusY=20), unit(2, 15, focusX=15, focusY=20)])
check("units still pointing straight down", slugs(qc.unfocused(plumb)), ["unfocused"])
# ⭐ ONE finding for the plot, not one per unit. On a rep plot this is every unit
# in the house, and 201 identical lines is not a report.
check("...rolled up into one finding", len(qc.unfocused(plumb)), 1)
check("...that still lists them", len(qc.unfocused(plumb)[0].units), 2)

leftover = plot([unit(1, 5), unit(2, 15), unit(200, 25)])
check("a unit 200 among three", slugs(qc.unit_numbering(leftover)),
      ["unit-out-of-range"])
# ⚠ A WARNING on purpose: numbering stage right 1-10 and stage left 21-30 is
# real practice and reads better on a hang sheet than one long run. What this
# catches is the leftover from an import, not a scheme.
check("...is a warning", qc.unit_numbering(leftover)[0].level, "warning")
check("1, 2, 3 is quiet", qc.unit_numbering(CLEAN), [])

check("a unit with no channel",
      slugs(qc.missing_channels(plot([unit(1, 5, channel=None)]))), ["no-channel"])

ganged = plot([unit(1, 5, address=12), unit(2, 15, address=12)])
check("two units on one address", slugs(qc.shared_addresses(ganged)),
      ["shared-address"])
# ⚠ NOT an error. Four Shakespeares ganged on one cyc dimmer share an address
# because they are one light as far as the desk is concerned. The same thing on
# an LED fixture is a patching slip, and the file does not say which it is.
check("...is a warning", qc.shared_addresses(ganged)[0].level, "warning")

check("a colour that is not a gel",
      slugs(qc.colours(plot([unit(1, 5, color="NC/Temp")]))), ["not-a-gel"])
# ⭐ The gel fix of 2026.10.13: punctuation is not a different filter.
check("R-33 is R33 and not a finding",
      qc.colours(plot([unit(1, 5, color="R-33")])), [])

check("a unit trimmed off its position",
      slugs(qc.trims(plot([unit(1, 5, trim=14)]))), ["trim-mismatch"])
# ⚠ A RAKED position carries a trim per leg, and a unit may legitimately match
# any of them — comparing against the first leg would flag half a catwalk.
raked = plot([unit(1, 5, trim=50), unit(2, 15, trim=47, position="#3 Catwalk")],
             positions=[{"name": "#1 ELECTRIC", "x1": 0, "y1": 20, "x2": 40,
                         "y2": 20, "trim": 50},
                        {"name": "#3 Catwalk", "x1": 0, "y1": 20, "x2": 40,
                         "y2": 20, "trim": 47}])
check("each leg's own trim is accepted", qc.trims(raked), [])

print("\n⭐ the report, and what the exit code means")
found = qc.check(plot([unit(1, 5), unit(1, 15), unit(2, 25, channel=None)]))
check("errors sort before warnings", [f.level for f in found],
      ["error", "warning"])
check("the error is named in the text", "[duplicate-unit]" in qc.report(found), True)
long_list = qc.report([qc.Finding("warning", "x", "many", [str(n) for n in range(20)])])
check("a long list is truncated", "and 14 more" in long_list, True)

print("\n🔴 the shipped samples")
demo = json.load(open(os.path.join(HERE, "..", "samples", "demo.plot.json"),
                      encoding="utf-8"))
# ⚠ THE ONE THAT MATTERS. demo.plot.json is what a stranger opens; it must not
# greet them with a list of complaints about itself.
check("demo.plot.json has no errors", slugs(qc.check(demo), "error"), [])
check("...and no warnings either", slugs(qc.check(demo), "warning"), [])

big = json.load(open(os.path.join(HERE, "..", "samples",
                                  "Sample Big House.plot.json"), encoding="utf-8"))
found = qc.check(big)
# 🔴 THE REGRESSION GUARD. Three duplicate units and 201 focus heights at the
# deck, fixed 2026.10.13. A sample that ships is a sample that gets copied.
check("Big House has no errors", slugs(found, "error"), [])
check("...on all 201 instruments", len(big["instruments"]), 201)
# ⚠ The warnings that remain are true, and naming them here means a NEW one
# shows up as a failure rather than disappearing into a list nobody reads.
check("...and the warnings are the known three", slugs(found, "warning"),
      ["no-channel", "not-a-gel", "unfocused"])
check("every finding names at least one unit", all(f.units for f in found), True)

print("\n⭐ and the fixes themselves, by name")
units = {(i.get("position"), str(i.get("unit"))): i for i in big["instruments"]}
# A unit added between 10 and 11, which is what a suffix is for.
check("#3 ELECTRIC has a 10A", ("#3 ELECTRIC", "10A") in units, True)
check("#4 ELECTRIC has one too", ("#4 ELECTRIC", "10A") in units, True)
# ⭐ It sorts where it hangs: between unit 10 at x=65.9 and unit 11 at x=57.0.
pipe = [i for i in big["instruments"]
        if (i.get("position") or "").strip() == "#3 ELECTRIC"]
check("...and 10A sits between 10 and 11",
      [i["unit"] for i in sorted(pipe, key=lambda i: positions.unit_key(i["unit"]))
       if positions.unit_key(i["unit"])[0] in (10, 11)], [10, "10A", 11])
# The one certain fix: 200 sat in the slot where 4 was missing.
cat = sorted(i["unit"] for i in big["instruments"]
             if (i.get("position") or "").strip() == "#4 Catwalk UPPER")
check("#4 Catwalk UPPER runs 1-28 with no gap", cat, list(range(1, 29)))
rail = sorted(i["unit"] for i in big["instruments"]
              if (i.get("position") or "").strip() == "Balcony Rail")
check("Balcony Rail runs 1-16", rail, list(range(1, 17)))

print("\n🔴 and nothing is focused at the deck any more")
# ⚠ THE ONE THAT WAS WORTH FINDING. Blank means head height — `focusH ?? 5.5`.
# Zero is a number, so it travels: on a 30' electric that is a 30' throw where
# the truth is 24'-6", and every pool on every sheet was the wrong size.
check("no focus height is 0",
      [i.get("focusH") for i in big["instruments"] if i.get("focusH") == 0], [])
check("every instrument states one",
      all(i.get("focusH") is not None for i in big["instruments"]), True)
check("...and demo does too",
      all(i.get("focusH") is not None for i in demo["instruments"]), True)
# ⭐ But the side light keeps the heights it was given. A mid lands at 3'-6" and
# a shin at 1'-6"; overwriting those with head height would be the opposite bug.
check("demo's side light is untouched",
      sorted({i["focusH"] for i in demo["instruments"]}), [1.5, 3.5, 5.5])

print("\n🔴 the exit code, which is what the CI gate actually reads")
# ⚠ A GATE THAT CANNOT FAIL IS NOT A GATE. The suites above test qc.check(); CI
# runs `python -m plotedit.qc`, and what it reads is main()'s return value. Those
# are two different things, and only one of them is wired to the gate.
import contextlib                                       # noqa: E402
import io                                               # noqa: E402
import json as _json                                    # noqa: E402
import tempfile                                         # noqa: E402


def exits(paths):
    """main()'s return value, with its report swallowed. ⚠ The report is 30
    lines on a real plot, and burying the pass/fail lines of a suite in it is
    how a failure stops being seen."""
    with contextlib.redirect_stdout(io.StringIO()):
        return qc.main(paths)


with tempfile.TemporaryDirectory() as tmp:
    def wrote(name, plot):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(plot, fh)
        return path

    good = wrote("good.plot.json", CLEAN)
    bad = wrote("bad.plot.json", plot([unit(9, 5), unit(9, 15), unit(10, 25)]))
    warns = wrote("warns.plot.json", plot([unit(1, 5, channel=None)]))

    check("a clean plot exits 0", exits([good]), 0)
    check("an ERROR exits 1", exits([bad]), 1)
    # ⭐ THE WHOLE REASON THE SPLIT EXISTS. Big House has three warnings today and
    # the gate is green. If warnings failed it, the gate would have to come out.
    check("a WARNING exits 0", exits([warns]), 0)
    check("one bad file among good ones still exits 1",
          exits([good, bad, warns]), 1)
    check("no arguments is a usage error, not a pass", exits([]), 2)
    # ⚠ And the files CI actually names, through the same entry point.
    here = os.path.join(HERE, "..", "samples")
    check("the shipped samples pass the gate itself",
          exits([os.path.join(here, "demo.plot.json"),
                 os.path.join(here, "Sample Big House.plot.json")]), 0)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
