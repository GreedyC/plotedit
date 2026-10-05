/** Run: cd web && npm run test:cards
 *
 * #88 rolls a position card up to one line. Jerry: "it makes it annoying to
 * work" — eleven open cards is a panel you scroll rather than read.
 *
 * 🔴 THE DANGER IN THAT FEATURE IS NOT THE LAYOUT, IT IS THE SILENCE. Each card
 * carries a note, and two of the things in that note cost real money in the
 * room: a trim above the ceiling, and two units on one position sharing a number
 * so the paperwork cannot tell them apart. Hide the card and you hide those —
 * the panel would get easier to use and quietly stop warning anybody, which is
 * the trade this file exists to refuse.
 *
 * So the shut card and the open card read the SAME function, and `redOnly()`
 * decides what survives. These tests are about that contract, not about pixels:
 * every red note must reach a shut card, and nothing that is merely informative
 * should.
 */
import { positionNotes, redOnly } from "./positions.js";
import { duplicateNames, type Plot, type Position } from "./plot.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(54)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

const RED = "\u{1F534}";

function plotWith(positions: Position[], instruments: Plot["instruments"] = [],
                  gridHeight?: number): Plot {
  return {
    formatVersion: 1, show: "T",
    room: { width: 30, depth: 40, ...(gridHeight !== undefined ? { gridHeight } : {}) },
    positions, instruments,
  };
}
const pipe = (name: string, extra: Partial<Position> = {}): Position => ({
  name, type: "electric", trim: 14, x1: -10, y1: 8, x2: 10, y2: 8, ...extra,
});
const notesFor = (p: Position, plot: Plot) =>
  positionNotes(p, plot, duplicateNames(plot.positions));

console.log("an ordinary pipe says something, and none of it is red");
{
  const p = pipe("ELECTRIC 1");
  const plot = plotWith([p], [], 20);
  const bits = notesFor(p, plot);
  check("it says something", bits.length > 0, true);
  check("nothing is red", redOnly(bits), []);
  check("it admits it has no circuits",
        bits.some(b => b.includes("no circuits recorded")), true);
}

console.log("\n🔴 a trim through the ceiling is red, and survives the roll-up");
{
  const p = pipe("ELECTRIC 1", { trim: 18 });
  const plot = plotWith([p], [], 15);
  const bits = notesFor(p, plot);
  const red = redOnly(bits);
  check("one red note", red.length, 1);
  check("...and it says what is wrong",
        red[0]?.includes("ABOVE THE 15' CEILING"), true);
  check("...and that it cannot be hung", red[0]?.includes("cannot be hung"), true);
}

console.log("\n⚠ but a trim that is merely TIGHT is not red — it is advice");
{
  // 1'-6" is what a Source Four and its clamp need. Close enough to warn about,
  // not wrong. Reds are for things that are actually broken.
  const p = pipe("ELECTRIC 1", { trim: 14.5 });
  const plot = plotWith([p], [], 15);
  const bits = notesFor(p, plot);
  check("the advice is there", bits.some(b => b.includes("Source Four")), true);
  check("...and it is NOT red, so a shut card stays quiet", redOnly(bits), []);
}

console.log("\n🔴 two units sharing a number is red");
{
  const p = pipe("ELECTRIC 1");
  const plot = plotWith([p], [
    { position: "ELECTRIC 1", unit: 3, type: "S4 26", channel: 1 },
    { position: "ELECTRIC 1", unit: 3, type: "S4 26", channel: 2 },
  ] as Plot["instruments"], 20);
  const red = redOnly(notesFor(p, plot));
  check("one red note", red.length, 1);
  check("...naming the unit", red[0]?.includes("3"), true);
  check("...and why it matters",
        red[0]?.includes("paperwork cannot tell them apart"), true);
}

console.log("\n⚠ a SHARED NAME is allowed, so it is stated and not reddened");
{
  // A V or an L is two segments of one position. That is how you say it.
  const a = pipe("BOOM", { x1: -10, y1: 4, x2: -10, y2: 10 });
  const b = pipe("BOOM", { x1: 10, y1: 4, x2: 10, y2: 10 });
  const plot = plotWith([a, b], [], 20);
  const bits = notesFor(a, plot);
  check("it says they are one position",
        bits.some(x => x.includes("shares its name")), true);
  check("...and does not treat that as an error", redOnly(bits), []);
}

console.log("\n🔴 the contract the shut card depends on");
{
  // Everything red, in one position, at once.
  const p = pipe("ELECTRIC 1", { trim: 18 });
  const plot = plotWith([p], [
    { position: "ELECTRIC 1", unit: 2, type: "S4 26", channel: 1 },
    { position: "ELECTRIC 1", unit: 2, type: "S4 26", channel: 2 },
  ] as Plot["instruments"], 15);
  const bits = notesFor(p, plot);
  const red = redOnly(bits);
  check("both reds survive", red.length, 2);
  // ⭐ The two directions of the contract, which is the whole point:
  check("every red note in the card reaches the shut card",
        bits.filter(b => b.includes(RED)).length, red.length);
  check("redOnly invents nothing", red.every(r => bits.includes(r)), true);
  check("...and drops everything that is not red",
        red.every(r => r.includes(RED)), true);
  check("the card does say more than the shut line", bits.length > red.length, true);
}

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
