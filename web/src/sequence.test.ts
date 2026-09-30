/** Numbering a run by clicking. Rules only — see `sequence.ts`.
 *
 * ⚠ The verdict is at the BOTTOM of this file and nowhere else. Twice in one day
 * a suite in this repo printed its verdict in the MIDDLE, so anything appended
 * ran without affecting the exit code — it could print failures and exit 0.
 */
import { startSeq, seqClick, clickLine, seqReport, runIndices,
         type Seq, type SeqUnit } from "./sequence.js";

let fails = 0;
function check(what: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${what.padEnd(52)} ${JSON.stringify(got)}`);
  if (!ok) console.log(`       wanted ${JSON.stringify(want)}`);
}

/** What main.ts does with an accepted click, so the report sees real data. */
function click(seq: Seq, insts: SeqUnit[], index: number) {
  const r = seqClick(seq, insts, index);
  if (r.ok) insts[index]!.unit = r.to;
  return r;
}

console.log("\nthe run is found by name");
{
  const insts: SeqUnit[] = [
    { position: "Electric 1", unit: 1 },
    { position: "Cove", unit: 1 },
    { position: "electric 1", unit: 2 },   // same name, different case
    { position: "Cove", unit: 2 },
  ];
  check("by name, case-insensitively", runIndices(insts, "Electric 1"), [0, 2]);
  check("a trailing space is the same name", runIndices(insts, " cove "), [1, 3]);
  check("an unknown name is empty", runIndices(insts, "nope"), []);
}

console.log("\none click at a time");
{
  const insts: SeqUnit[] = [
    { position: "E1", unit: 9 }, { position: "E1", unit: 8 }, { position: "E2", unit: 1 },
  ];
  const seq = startSeq("E1", 1);
  const a = click(seq, insts, 0);
  check("assigns the start number", a.ok && a.to, 1);
  check("reports the number it overwrote", a.ok && a.from, 9);
  check("advances", seq.next, 2);
  check("not the last unit yet", a.ok && a.last, false);

  const wrong = click(seq, insts, 2);
  check("refuses a unit on another position", wrong.ok, false);
  check("...and says which position it is on",
        !wrong.ok && wrong.why.includes('"E2"'), true);
  check("...and cites the rule", !wrong.ok && wrong.why.includes("2.3.2"), true);
  check("a refusal does not consume a number", seq.next, 2);

  const twice = click(seq, insts, 0);
  check("refuses a second click on the same unit", twice.ok, false);
  check("...saying what it already got",
        !twice.ok && twice.why.includes("already numbered 1"), true);
  check("a double click does not leave a gap", seq.next, 2);

  const gone = click(seq, insts, 99);
  check("refuses an index that is not there", gone.ok, false);

  const b = click(seq, insts, 1);
  check("the last unit on the run says so", b.ok && b.last, true);
}

console.log("\nthe starting number and the step are the user's");
{
  const insts: SeqUnit[] = [{ position: "E1" }, { position: "E1" }, { position: "E1" }];
  const seq = startSeq("E1", 101, 10);
  check("starts where told", click(seq, insts, 0).ok && insts[0]!.unit, 101);
  check("steps by what it was given", click(seq, insts, 1).ok && insts[1]!.unit, 111);
  check("and again", click(seq, insts, 2).ok && insts[2]!.unit, 121);
}

console.log("\nwhat the status line says");
{
  const insts: SeqUnit[] = [{ position: "E1", unit: 7 }, { position: "E1" }];
  const seq = startSeq("E1", 3);
  const a = click(seq, insts, 0);
  const line = a.ok ? clickLine(a) : "";
  // ⭐ The OLD number is stated because a number being overwritten is the risk.
  check("states the number it replaced", line.includes("unit 7 → 3"), true);
  check("says what comes next", line.includes("Next: 4"), true);
  check("offers the one-click undo", line.includes("⌘Z"), true);

  const b = click(seq, insts, 1);
  const last = b.ok ? clickLine(b) : "";
  check("an unnumbered unit is not called unit undefined",
        last.includes("unnumbered → 4"), true);
  check("the last click says the run is done",
        last.includes("every unit on the run"), true);
  check("...and stops offering Next", last.includes("Next:"), false);
}

console.log("\nthe verdict at the end");
{
  const insts: SeqUnit[] = [{ position: "E1", unit: 1 }, { position: "E1", unit: 2 }];
  check("nothing clicked, nothing claimed",
        seqReport(startSeq("E1", 1), insts), "E1: nothing was numbered.");
}
{
  // Reordering a run of 3 completely: every number is touched, and mid-pass
  // there are duplicates that resolve. The verdict must be clean.
  const insts: SeqUnit[] = [
    { position: "E1", unit: 1 }, { position: "E1", unit: 2 }, { position: "E1", unit: 3 },
  ];
  const seq = startSeq("E1", 1);
  click(seq, insts, 2); click(seq, insts, 1); click(seq, insts, 0);
  const rep = seqReport(seq, insts);
  check("a full pass reports the count", rep.includes("numbered 3 units"), true);
  // 🔴 THE POINT: after the first click two units held 1. Reporting that mid-pass
  // would fire on nearly every pass, which is how a warning stops being read.
  check("a full pass flags nothing", rep.includes("🔴"), false);
  check("the units came out reversed", insts.map(i => i.unit), [3, 2, 1]);
}
{
  // 🔴 THE ABANDONED PASS — the one case that genuinely leaves a broken run.
  const insts: SeqUnit[] = [
    { position: "E1", unit: 1 }, { position: "E1", unit: 2 }, { position: "E1", unit: 3 },
  ];
  const seq = startSeq("E1", 2);
  click(seq, insts, 0);                       // unit 1 becomes 2; the real 2 remains
  const rep = seqReport(seq, insts);
  check("says how many were done", rep.includes("numbered 1 unit"), true);
  check("says how many still carry old numbers",
        rep.includes("2 still have their old numbers"), true);
  check("flags the duplicate it left", rep.includes("🔴"), true);
  check("...naming the number", rep.includes("number 2 is now used twice"), true);
}

console.log("\n⭐ the V that sort-based renumbering gets wrong");
{
  // A '>' shaped cove: TWO positions sharing one name, legs covering the same
  // ground. Renumbering it by RP-2 §2.3.2's stage-left rule was MEASURED giving
  // odds down one leg and evens back up the other — see docs/NEXT.md:
  //     leg A  x = 0, 4, 8, 12    →  units 1, 3, 5, 7
  //     leg B  x = 14, 10, 6, 2   →  units 8, 6, 4, 2
  // Clicking along the run instead produces the order the designer walked.
  const insts: SeqUnit[] = [
    { position: "Cove", unit: 1 }, { position: "Cove", unit: 2 },
    { position: "Cove", unit: 3 }, { position: "Cove", unit: 4 },   // leg A
    { position: "Cove", unit: 1 }, { position: "Cove", unit: 2 },
    { position: "Cove", unit: 3 }, { position: "Cove", unit: 4 },   // leg B
  ];
  // ⭐ ONE RUN, both legs — which is the case a single sort key cannot order.
  check("a shared name is one run of 8", runIndices(insts, "Cove").length, 8);

  const seq = startSeq("Cove", 1);
  for (const i of [0, 1, 2, 3, 4, 5, 6, 7]) click(seq, insts, i);
  check("walking the pipe numbers 1 to 8", insts.map(i => i.unit), [1,2,3,4,5,6,7,8]);
  const rep = seqReport(seq, insts);
  check("no duplicates left across the legs", rep.includes("🔴"), false);
  check("nothing left unnumbered", rep.includes("still"), false);
}

if (fails) { console.log(`\n${fails} FAILED`); process.exit(1); }
console.log("\nall passed");
