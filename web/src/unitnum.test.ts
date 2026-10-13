/**
 * A unit number can be "10A", and it sorts between 10 and 11.
 *
 *    cd web && npm run test:units
 *
 * ⭐ WHY THE SUFFIX EXISTS. Adding a unit between 10 and 11 is ordinary — the
 * plot is drawn, the rig is hung, and one more light is wanted in the middle of
 * the pipe. On a hang sheet that light is 10A, because the alternative is
 * renumbering every unit above it and handing the electrician a second document
 * that disagrees with the one taped to the pipe. (Jerry, 2026.10.13: "yes 10A
 * should be allowed - thats the standard".)
 *
 * 🔴 SORTING IS THE WHOLE POINT. If 10A sorts last the schedule is in a
 * different order from the rig, and the number may as well have been 19.
 *
 * ⚠ Mirrored by server/plotedit/positions.py — unit_key, unit_label, next_unit.
 * The two have to agree, because the plot sorts in the browser and the schedule
 * sorts in Python. test_unit_numbers.py runs the same cases.
 */
import { unitKey, unitLabel, compareUnits, parseUnit, nextUnit } from "./plot.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(50)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

console.log("a unit number, read");
check("a plain number", unitKey(10), [10, ""]);
check("a suffixed one", unitKey("10A"), [10, "A"]);
check("case does not matter", unitKey("10a"), [10, "A"]);
check("space does not matter", unitKey(" 7 "), [7, ""]);
check("a number written as text", unitKey("7"), [7, ""]);
// ⚠ Unreadable sorts LAST rather than throwing. A plot with a typo in one cell
// still draws, and the QC pass is what says the cell is wrong.
check("nothing at all", unitKey(undefined), [Infinity, ""]);
check("something that is not a number", unitKey("cyc"), [Infinity, "CYC"]);

console.log("\n🔴 and it sorts where it hangs");
check("10A is between 10 and 11",
      [11, "10A", 10, 9, "9B"].sort(compareUnits), [9, "9B", 10, "10A", 11]);
check("a whole pipe stays in order",
      [3, "1A", 2, 1, "2B", "2A"].sort(compareUnits), [1, "1A", 2, "2A", "2B", 3]);
// ⚠ NOT a string sort, which is the obvious wrong answer: "10" < "9" as text,
// so a text sort puts unit 10 before unit 9 and the hang sheet is unusable.
check("9 before 10, not after", [10, 9].sort(compareUnits), [9, 10]);
check("...and 100 after 99", [100, 99].sort(compareUnits), [99, 100]);
check("unreadable goes last", ["cyc", 2, 1].sort(compareUnits), [1, 2, "cyc"]);

console.log("\nthe canonical label, so one number is one light");
check("a number", unitLabel(9), "9");
check("a suffix is upper case", unitLabel("10a"), "10A");
check("...and so is a lone one", unitLabel("3b"), "3B");
check("padding is trimmed", unitLabel(" 12 "), "12");
check("nothing is empty, not \"undefined\"", unitLabel(undefined), "");
check("an empty string is empty too", unitLabel(""), "");
// ⭐ 10 and "10" MUST agree, or a plot that has been through the API holds two
// unit 10s that nothing can tell apart.
check("10 and \"10\" are the same label", unitLabel(10) === unitLabel("10"), true);

console.log("\nwhat the Unit box accepts");
check("a number stays a NUMBER", parseUnit("11"), 11);
check("...so editing a plot does not restring every unit",
      typeof parseUnit("11"), "number");
check("a suffix becomes a string", parseUnit("10a"), "10A");
check("empty clears the field", parseUnit("  "), undefined);
// ⚠ null is "that is not a unit number", and the inspector refuses LOUDLY on it
// rather than clearing the field. A light with no number cannot be addressed by
// the schedule, the hookup or the focus chart.
check("a word is refused", parseUnit("cyc"), null);
check("two letters are refused", parseUnit("10AB"), null);
check("a letter first is refused", parseUnit("A10"), null);
check("a decimal is refused", parseUnit("10.5"), null);

console.log("\nthe next free number");
check("an empty pipe starts at 1", nextUnit([]), 1);
check("one past the highest", nextUnit([{ unit: 1 }, { unit: 2 }]), 3);
// ⭐ A SUFFIX DOES NOT TAKE A SLOT. 10A shares its number with 10, so a pipe of
// 10, 10A, 11 offers 12 next — not 11, which is taken.
check("10A counts as 10", nextUnit([{ unit: 10 }, { unit: "10A" }, { unit: 11 }]), 12);
check("...even on its own", nextUnit([{ unit: "10A" }]), 11);
check("unreadable numbers are ignored", nextUnit([{ unit: "cyc" }, { unit: 4 }]), 5);
check("so is a missing one", nextUnit([{ unit: undefined }, { unit: 4 }]), 5);
check("all unreadable starts at 1", nextUnit([{ unit: "cyc" }]), 1);

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("a unit number can be 10A, and it sorts where it hangs");
