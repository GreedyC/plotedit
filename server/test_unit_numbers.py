#!/usr/bin/env python3
"""A unit number can be "10A", and it sorts between 10 and 11.

    cd server && python3 test_unit_numbers.py

⭐ WHY THE SUFFIX EXISTS. Adding a unit between 10 and 11 is ordinary — the plot
is drawn, the rig is hung, and one more light is wanted in the middle of the
pipe. On a hang sheet that light is 10A, because the alternative is renumbering
every unit above it and handing the electrician a second document that disagrees
with the one taped to the pipe. (Jerry, 2026.10.13: "yes 10A should be allowed -
thats the standard".)

🔴 SORTING IS THE WHOLE POINT. If 10A sorts last then the schedule is in a
different order from the rig, and the number may as well have been 19 on the end
of the run.

⚠ THE PLOT SORTS IN THE BROWSER AND THE SCHEDULE SORTS IN PYTHON, so the two
implementations have to agree. The cases below are the same ones as
web/src/unitnum.test.ts, deliberately — if one is changed and the other is not,
a plot drawn in one order prints in another.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plotedit import exports, positions as P    # noqa: E402

FAILS = []
INF = float("inf")


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<50} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("a unit number, read")
check("a plain number", P.unit_key(10), (10, ""))
check("a suffixed one", P.unit_key("10A"), (10, "A"))
check("case does not matter", P.unit_key("10a"), (10, "A"))
check("space does not matter", P.unit_key(" 7 "), (7, ""))
check("a number written as text", P.unit_key("7"), (7, ""))
# ⚠ Unreadable sorts LAST rather than raising. A plot with a typo in one cell
# still prints, and the QC pass is what says the cell is wrong.
check("nothing at all", P.unit_key(None), (INF, ""))
check("something that is not a number", P.unit_key("cyc"), (INF, "CYC"))

print("\n🔴 and it sorts where it hangs")
check("10A is between 10 and 11",
      sorted([11, "10A", 10, 9, "9B"], key=P.unit_key), [9, "9B", 10, "10A", 11])
check("a whole pipe stays in order",
      sorted([3, "1A", 2, 1, "2B", "2A"], key=P.unit_key),
      [1, "1A", 2, "2A", "2B", 3])
# ⚠ NOT a text sort, which is the obvious wrong answer: "10" < "9" as text, so a
# text sort puts unit 10 before unit 9 and the hang sheet is unusable.
check("9 before 10, not after", sorted([10, 9], key=P.unit_key), [9, 10])
check("...and 100 after 99", sorted([100, 99], key=P.unit_key), [99, 100])
check("unreadable goes last", sorted(["cyc", 2, 1], key=P.unit_key), [1, 2, "cyc"])

print("\nthe canonical label, so one number is one light")
check("a number", P.unit_label(9), "9")
check("a suffix is upper case", P.unit_label("10a"), "10A")
check("padding is trimmed", P.unit_label(" 12 "), "12")
check("nothing is empty, not 'None'", P.unit_label(None), "")
check("an empty string is empty too", P.unit_label(""), "")
# ⭐ 10 and "10" MUST agree, or a plot that has been through the API holds two
# unit 10s that nothing can tell apart.
check("10 and '10' are the same label", P.unit_label(10) == P.unit_label("10"), True)
# ⚠ A float that is a whole number prints as an integer. JSON has no int/float
# split, so a plot round-tripped through some other tool can hand us 10.0 — and
# "unit 10.0" on a hang sheet is not a unit number.
check("10.0 is unit 10", P.unit_label(10.0), "10")

print("\nthe next free number")
check("an empty pipe starts at 1", P.next_unit([]), 1)
check("one past the highest", P.next_unit([{"unit": 1}, {"unit": 2}]), 3)
# ⭐ A SUFFIX DOES NOT TAKE A SLOT. 10A shares its number with 10, so a pipe of
# 10, 10A, 11 offers 12 next — not 11, which is taken.
check("10A counts as 10",
      P.next_unit([{"unit": 10}, {"unit": "10A"}, {"unit": 11}]), 12)
check("...even on its own", P.next_unit([{"unit": "10A"}]), 11)
check("unreadable numbers are ignored",
      P.next_unit([{"unit": "cyc"}, {"unit": 4}]), 5)
check("all unreadable starts at 1", P.next_unit([{"unit": "cyc"}]), 1)

print("\n🔴 and the schedule prints in that order")
# ⚠ THE ONE THAT WOULD ACTUALLY BE NOTICED. _sorted_for_schedule used _num(),
# which reads "10A" as unreadable and sends it to the END of the pipe — so a
# unit hung between 10 and 11 printed after unit 23, and the paper disagreed
# with the rig.
pipe = [{"position": "#1 ELECTRIC", "unit": u, "type": "S4 26"}
        for u in (11, "10A", 10, 9)]
check("a suffixed unit prints between its neighbours",
      [i["unit"] for i in exports._sorted_for_schedule(pipe)], [9, 10, "10A", 11])
# ⭐ Position first, then unit — the order someone hangs in.
mixed = [{"position": "#2 ELECTRIC", "unit": 1}, {"position": "#1 ELECTRIC", "unit": "2A"},
         {"position": "#1 ELECTRIC", "unit": 1}, {"position": "#1 ELECTRIC", "unit": 2}]
check("position first, then unit",
      [(i["position"][:2], i["unit"]) for i in exports._sorted_for_schedule(mixed)],
      [("#1", 1), ("#1", 2), ("#1", "2A"), ("#2", 1)])

print("\n⭐ renumbering still writes plain integers")
# A one-press renumber sorts by geometry and numbers 1..n. It cannot invent a
# suffix and should not try — a suffix is a human saying "this one went in
# later", which is exactly what a geometry sort does not know.
pos = {"name": "#1 ELECTRIC", "type": "electric",
       "x1": 0, "y1": 20, "x2": 40, "y2": 20, "trim": 20}
on = [{"position": "#1 ELECTRIC", "unit": "10A", "x": 10, "y": 20},
      {"position": "#1 ELECTRIC", "unit": 10, "x": 20, "y": 20},
      {"position": "#1 ELECTRIC", "unit": 11, "x": 30, "y": 20}]
count, warn = P.number(on, pos)
check("every unit on the run was numbered", count, 3)
check("...as integers, suffix and all",
      sorted(i["unit"] for i in on), [1, 2, 3])
check("...and nothing was flagged", warn, None)

print("\n⚠ and the API door normalises, because it is the other way in")
# 🔴 Union[int, str] accepts the STRING "10" as a string. A client that posts
# its unit numbers as text would give the plot a unit "10" beside a unit 10 —
# two records the paperwork cannot tell apart, since it addresses a light as
# "position, number".
from plotedit import api                        # noqa: E402  (slow import)


def door(v):
    return api.Instrument(unit=v, type="S4 26", x=1, y=2).unit


check("a number is left alone", door(9), 9)
check("'10' becomes 10", door("10"), 10)
check("...and is a real int", isinstance(door("10"), int), True)
check("padding goes", door(" 11 "), 11)
check("a suffix survives", door("10A"), "10A")
check("...and is folded up", door("10a"), "10A")
check("empty is nothing", door(""), None)
check("nothing is nothing", door(None), None)
# ⭐ NOT REJECTED. The door preserves what it was given and the QC pass is what
# says the cell is wrong — refusing here would lose a plot on one bad cell.
check("something that is not a unit number is kept", door("cyc"), "cyc")

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
