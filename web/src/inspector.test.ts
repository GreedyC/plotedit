/**
 * The lamp dropdown offers what this fixture can be computed with, and nothing else.
 *
 *    cd web && npm run test:lamps
 *
 * 🔴 WHAT WENT WRONG. The lamp list was one global copy of LAMP_MF's keys,
 * offered on every barrel. So an Altman Shakespeare offered HPL 750 — and
 * picking it BLANKED THE FOOTCANDLES, because there is no HPL multiplier for an
 * Altman barrel and never will be. 194 of the 201 units in Sample Big House are
 * Shakespeares, and the dropdown's only safe entry was the blank one.
 *
 * ⭐ The list is the server's answer now (`/fixtures` → `lamps`), per fixture.
 * server/test_lamp_list.py checks the Python half; this checks what the panel
 * does with it, which is the half with the judgement calls in it.
 */
import assert from "node:assert/strict";
import { lampsFor, inertBecause, FIELDS, type InspectorDeps } from "./inspector.js";
import type { Instrument } from "./plot.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown): void {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(52)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

// The server's answers, as /fixtures gives them.
const TABLE: Record<string, { lamps: string[]; modes: string[] }> = {
  "S4 26": { lamps: ["HPL 750", "HPL 575", "HPL 375"], modes: [] },
  "Altman Shakespeare 30": { lamps: ["GLC"], modes: [] },
  "Lustr 26 EDLT": { lamps: [], modes: ["Boost Full", "Regulated 3200K"] },
  "S4 Zoom 15-30 @23": { lamps: [], modes: [] },
};
const deps = {
  fixtures: Object.keys(TABLE), modes: [],
  lampsFor: (t: string) => TABLE[t]?.lamps ?? [],
  modesFor: (t: string) => TABLE[t]?.modes ?? [],
  onPhotometricChange: () => {}, onPaperworkChange: () => {},
} as unknown as InspectorDeps;

const unit = (type: string, lamp?: string) =>
  ({ unit: 1, type, x: 0, y: 0, lamp } as Instrument);
const lampField = FIELDS.find(f => f.key === "lamp")!;

console.log("the list is per fixture, not one list for everything");
check("an S4 offers its HPLs", lampsFor(unit("S4 26"), deps),
      ["HPL 750", "HPL 575", "HPL 375"]);
// 🔴 THE BUG. Before this, the Shakespeare's list was the S4's list.
check("a Shakespeare offers GLC", lampsFor(unit("Altman Shakespeare 30"), deps), ["GLC"]);
check("...and not one HPL",
      lampsFor(unit("Altman Shakespeare 30"), deps).some(l => l.includes("HPL")), false);
check("an LED offers none", lampsFor(unit("Lustr 26 EDLT"), deps), []);
check("a type the server does not know offers none", lampsFor(unit("Patt 23"), deps), []);

console.log("\n⚠ but a lamp the plot ALREADY holds stays on the list");
// Dropping it would make the select show a blank where the file says HPL 575 —
// which hides the very thing that needs fixing: that unit has no footcandles,
// and the wrong lamp is why. A plot read from someone else's paperwork is
// exactly where this turns up.
check("a wrong lamp is appended, not dropped",
      lampsFor(unit("Altman Shakespeare 30", "HPL 575"), deps), ["GLC", "HPL 575"]);
check("...and the right one is not duplicated",
      lampsFor(unit("Altman Shakespeare 30", "GLC"), deps), ["GLC"]);
check("...even on a fixture with no list at all",
      lampsFor(unit("S4 Zoom 15-30 @23", "HPL 750"), deps), ["HPL 750"]);

console.log("\n⭐ and the row says which kind of empty it is");
// "No lamp" and "no published figures for any lamp" are different facts about
// the rig, and they send a reader to different places.
check("an LED's lamp row says there is no lamp",
      /no lamp in it/.test(inertBecause(lampField, unit("Lustr 26 EDLT"), deps) ?? ""), true);
check("a Zoom's says nothing is published",
      /No per-lamp figures are published/.test(
        inertBecause(lampField, unit("S4 Zoom 15-30 @23"), deps) ?? ""), true);
check("an S4's row is live", inertBecause(lampField, unit("S4 26"), deps), null);
check("a Shakespeare's row is live",
      inertBecause(lampField, unit("Altman Shakespeare 30"), deps), null);
// ⚠ A fixture with no published figures that nonetheless HOLDS a lamp is still
// live — there is something to see and something to clear.
check("...and so is a Zoom that holds one",
      inertBecause(lampField, unit("S4 Zoom 15-30 @23", "HPL 750"), deps), null);

console.log("\nthe mode row is the mirror of it, unchanged");
const modeField = FIELDS.find(f => f.key === "mode")!;
check("an S4's mode row is inert",
      /belongs to an LED engine/.test(inertBecause(modeField, unit("S4 26"), deps) ?? ""), true);
check("an LED's mode row is live", inertBecause(modeField, unit("Lustr 26 EDLT"), deps), null);

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("the lamp dropdown offers what the fixture can be computed with");
