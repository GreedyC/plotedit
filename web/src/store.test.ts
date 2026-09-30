/** Run: cd web && npm run test:store */
import { Store, snapToPosition } from "./store.js";
import { plotFileName, newPlot, isPlot, resolveEnds, runOf, lengthOf, angleOf,
         endsFromLengthAngle, duplicateNames, duplicateUnits, nextPositionName,
         type Plot } from "./plot.js";
import { feet } from "./details.js";
import { nextBoomHeight } from "./positions.js";
import { deleteMessage, describeUnit, sharedNameMessage,
         sharedNameRenumberNote } from "./confirm.js";
import { parseFeet } from "./feet.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(48)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

const base = (): Plot => ({
  formatVersion: 1, show: "T",
  room: { width: 33, depth: 38 },
  positions: [
    { name: "GRID C", x1: 0, y1: 20, x2: 33, y2: 20, trim: 14 },
    { name: "GRID D", x1: 0, y1: 24, x2: 33, y2: 24, trim: 14 },
  ],
  instruments: [
    { unit: 1, channel: 1, type: "S4 26", x: 5, y: 20 },
    { unit: 2, channel: 2, type: "S4 26", x: 10, y: 20 },
  ],
});

console.log("undo");
let s = new Store(base());
s.begin(null); s.update(0, { x: 7 });
check("edit applied", s.plot.instruments[0]!.x, 7);
check("dirty", s.dirty, true);
s.undo();
check("undo restores", s.plot.instruments[0]!.x, 5);
s.redo();
check("redo reapplies", s.plot.instruments[0]!.x, 7);

console.log("\nundo does not alias the live plot");
s = new Store(base());
s.begin(null); s.update(0, { x: 7 }); s.undo();
s.begin(null); s.update(0, { x: 9 });
check("the snapshot was a deep copy", s.plot.instruments[0]!.x, 9);
s.undo();
check("and still restores", s.plot.instruments[0]!.x, 5);

console.log("\na drag is ONE undo step");
s = new Store(base());
for (let i = 0; i < 50; i++) { s.begin("drag:0"); s.update(0, { x: 5 + i * 0.1 }); }
s.commit();
s.undo();
check("fifty moves collapse to one", +s.plot.instruments[0]!.x.toFixed(2), 5);
check("nothing left to undo", s.canUndo, false);

console.log("\nadd and remove");
s = new Store(base());
s.add({ unit: 3, type: "S4 36", x: 1, y: 1 });
check("added", s.plot.instruments.length, 3);
check("and selected", s.selected, 2);
s.remove(2);
check("removed", s.plot.instruments.length, 2);
check("selection follows", s.selected, 1);
s.undo();
check("undo brings it back", s.plot.instruments.length, 3);

console.log("\nsnap to a pipe — units hang on pipes, not in mid-air");
const p = base();
check("near GRID C snaps to it", snapToPosition(12, 20.4, p), { x: 12, y: 20, position: "GRID C" });
check("far from any pipe does not", snapToPosition(12, 22, p), { x: 12, y: 22, position: null });
check("picks the nearer of two", snapToPosition(12, 23.4, p).position, "GRID D");
check("just past the end clamps to the end", snapToPosition(33.6, 20, p),
      { x: 33, y: 20, position: "GRID C" });
// Far past the end must NOT snap — dragging a unit seven feet off the pipe and
// having it silently jump back is worse than leaving it where it was put.
check("far past the end does not snap", snapToPosition(40, 20, p).position, null);

console.log();


// ⚠ The verdict goes LAST. It used to sit in the middle of the file, so
// anything appended after it ran WITHOUT affecting the exit code — the suite
// could print failures and still exit 0. The same defect was found in two of the
// Python suites on 2026.09.23; verify_suites.py checks those, and did not cover
// these.
console.log("\na show title is not a filename");
// ⚠ Free text on one side, a filesystem on the other.
check("an ordinary title", plotFileName("Without Consent"), "Without Consent.plot.json");
check("a slash would make a directory", plotFileName("Without Consent: Act 2/3"),
      "Without Consent Act 2 3.plot.json");
check("punctuation only does NOT give a hidden dotfile", plotFileName("???"), "plot.plot.json");
check("nor does an empty title", plotFileName(""), "plot.plot.json");
check("runs of spaces collapse", plotFileName("A   B"), "A B.plot.json");
check("a very long title is cut", plotFileName("x".repeat(200)).length, 90);

console.log("\nshow and venue are editable, and undoable");
{
  const start = base();
  const s2 = new Store(structuredClone(start));
  s2.setMeta({ designer: "A N Other", studio: "Some Other Shop" });
  check("the designer is set", s2.plot.designer, "A N Other");
  check("...and the studio", s2.plot.studio, "Some Other Shop");
  check("...and the plot is dirty", s2.dirty, true);
  s2.undo();
  check("...and undo puts the old name back", s2.plot.designer, start.designer);

  // ⚠ A patch, not a replacement. Setting the width used to be the moment to
  // find out the rest of the room had gone with it.
  const w0 = s2.plot.room.depth;
  s2.setRoom({ width: 60 });
  check("the room width changes", s2.plot.room.width, 60);
  check("...and the depth is untouched", s2.plot.room.depth, w0);
  s2.undo();
  check("...and undo restores the width", s2.plot.room.width, start.room.width);
}

console.log("\nan empty box is NOT zero");
// 🔴 A grid height of 0 claims the ceiling is on the floor. Undefined means
// "not known", and the headroom checks already say so out loud rather than
// passing quietly — reading "" as 0 would turn a missing measurement into a
// confident, wrong one.
check("blank is unknown", feet(""), undefined);
check("nonsense is unknown too", feet("abc"), undefined);
check("zero is zero", feet("0"), 0);
check("a real number survives", feet("16.5"), 16.5);

console.log("\nadding a unit to a boom gives it a HEIGHT");
// 🔴 The bug: a boom position carries no trim, so `height: p.trim` was
// undefined — and an undefined height puts a unit in the elevation's NO HEIGHT
// RECORDED list and skips it in plan. The unit was in the file and on neither
// drawing. Jerry: "adding an instrument to a boom doesn't seem to work."
check("an empty boom starts at high side", nextBoomHeight([]), 12);
check("...or at the position's own trim if it has one", nextBoomHeight([], 16), 16);
check("the sample boom's next unit goes below the lowest",
      nextBoomHeight([12, 8, 4.5]), 1);   // gaps 4 and 3.5, mean 3.75 -> 0.75, snapped
check("a boom hung at 4ft intervals carries on at 4ft",
      nextBoomHeight([16, 12, 8]), 4);
check("one unit alone uses a sensible default step", nextBoomHeight([12]), 8);

// ⚠ NEVER the same height twice. Two units at one height on a boom are one
// point in plan and one mark on the elevation — the drawing would show one and
// the paperwork two, with nothing saying which was which.
{
  // Fill a boom until it refuses, and check the whole run: every height
  // distinct, every one on the boom, and it STOPS — a rule that keeps finding
  // room forever is one that is about to return a duplicate.
  const hs = [12, 8, 4.5];
  let adds = 0;
  for (;;) {
    const h = nextBoomHeight(hs);
    if (h === undefined) break;
    if (hs.includes(h)) { fails++; console.log(`  FAIL add ${adds + 1} repeated ${h}`); break; }
    if (h < 1) { fails++; console.log(`  FAIL add ${adds + 1} went below the deck: ${h}`); break; }
    hs.push(h);
    if (++adds > 40) { fails++; console.log("  FAIL it never refuses"); break; }
  }
  check("a 12ft boom takes several more units, all at distinct heights", adds > 3, true);
  check("...and then refuses instead of stacking", nextBoomHeight(hs), undefined);
  check("...having never repeated a height", new Set(hs).size, hs.length);
}
check("a boom with no room at all refuses", nextBoomHeight([2, 1]), undefined);

console.log("\nevery delete asks, and the question NAMES the thing");
// ⚠ "Are you sure?" on its own asks the reader to remember what they just
// clicked — which is exactly what someone about to delete the wrong thing has
// got wrong. The message has to say WHICH unit.
check("a unit is named by number, position and channel",
      describeUnit({ unit: 3, channel: 33, position: "GRID C", type: "S4 36" }),
      "unit 3 on GRID C (channel 33, S4 36)");
check("...and reads sensibly with nothing but a number",
      describeUnit({ unit: 7 }), "unit 7");
check("...and channel 0 is a channel, not a missing one",
      describeUnit({ unit: 7, channel: 0 }), "unit 7 (channel 0)");

check("the question leads with the subject",
      deleteMessage("unit 3 on GRID C").split("\n")[0], "Delete unit 3 on GRID C?");
check("...and says it can be undone",
      deleteMessage("unit 3").includes("undone"), true);
check("...and carries the consequence when there is one",
      deleteMessage("the position GRID C", "4 units will be KEPT.").includes("4 units"), true);

console.log("\nthe boxes take feet and inches, because the drawing prints them");
// 🔴 They were <input type="number">, which SILENTLY DISCARDS 1'6" — the field
// goes empty, the handler reads that as "clear this", and the value reverts to
// its default. Jerry set a focus height of 1'-6" and got no pool, because the
// focus height was never set.
for (const [typed, want] of [
  ["1'6\"", 1.5], ["1'-6\"", 1.5], ["1' 6\"", 1.5], ["1'6", 1.5],
  ["1'", 1], ["18\"", 1.5], ["1.5", 1.5], ["12", 12], ["-3", -3],
  ["5\u20326\u2033", 5.5],          // the prime marks a word processor produces
] as [string, number][]) {
  check(`${typed} is ${want}ft`, +(parseFeet(typed) as number).toFixed(4), want);
}
// ⚠ The sign belongs to the whole length: -1'6" is a foot and a half BELOW
// zero, not minus one foot plus six inches.
check("-1'6\" is -1.5, not -0.5", parseFeet("-1'6\""), -1.5);

// ⚠ Empty and nonsense are DIFFERENT. Empty clears a field; nonsense means the
// reader meant something and mistyped it, and must not silently wipe the value
// that was there.
check("empty means no value", parseFeet(""), undefined);
check("spaces are empty too", parseFeet("   "), undefined);
check("nonsense is refused, not treated as empty", parseFeet("about 6"), null);
check("...so is a stray word", parseFeet("6ft"), null);
check("...and 5'14\" is a typo, not 6'2\"", parseFeet("5'14\""), null);

console.log("\na new plot is empty, and honest about it");
{
  const p = newPlot("Studio Test");
  check("it is a valid plot", isPlot(p), true);
  check("named what was asked", p.show, "Studio Test");
  check("no instruments", p.instruments.length, 0);
  check("no positions", p.positions.length, 0);

  // 🔴 No designer, no studio. Those print in the TITLE BLOCK, and a new plot
  // inheriting whoever used the tool last would put one person's name on
  // another person's drawing.
  check("nobody's name on it", p.designer, undefined);
  check("nobody's studio either", p.studio, undefined);

  // ⚠ The room has a size because the canvas has to fit to something, but the
  // size is NOT a measurement and the plot says so — that text prints across
  // the top of the drawing until it is replaced.
  check("the room has a workable size", p.room.width > 0 && p.room.depth > 0, true);
  check("...and says it is not measured",
        (p.room.source ?? "").includes("NOT MEASURED"), true);

  check("two new plots do not share a room object", newPlot().room === p.room, false);
}

console.log("\nthree values decide which way a position runs");
// ⭐ Jerry, 2026.09.24: "we need to be able to add grid pipes that are US to DS
// — we could have x1 x2 y1 y2 and only require 3 values which would determine
// the direction." The form offered X1, Y1, X2 and wrote y2 = y1 behind the
// reader's back, so every position it could make ran stage-left to stage-right.
const R = (a?: number, b?: number, c?: number, d?: number, prev?: any) =>
  resolveEnds(a, b, c, d, prev);

check("all four given are taken as given", R(0, 20, 33, 20), { x1: 0, y1: 20, x2: 33, y2: 20 });
check("no Y2 runs it across", R(0, 20, 33), { x1: 0, y1: 20, x2: 33, y2: 20 });
check("no X2 runs it up and downstage", R(6, 10, undefined, 30),
      { x1: 6, y1: 10, x2: 6, y2: 30 });
check("neither is a point — which is a boom in plan", R(6, 10),
      { x1: 6, y1: 10, x2: 6, y2: 10 });
check("a raked position survives", R(0, 10, 20, 30), { x1: 0, y1: 10, x2: 20, y2: 30 });
check("no X1 is not a position", R(undefined, 10, 20, 30), null);

// 🔴 THE LENGTH SURVIVES THE TURN. Clearing X2 on a pipe that already runs
// across leaves no extent in EITHER direction, so a 33-foot electric would
// silently become a point. Blanking an axis has to TURN the pipe, not erase it
// — my first version did erase it, and the status line said "runs a point"
// while the hint promised it would run up and downstage.
const across = { x1: 0, y1: 36, x2: 33, y2: 36 };
check("clearing X2 turns a 33ft pipe rather than collapsing it",
      R(0, 36, undefined, 36, across), { x1: 0, y1: 36, x2: 0, y2: 69 });
check("...and clearing Y2 turns it back",
      R(0, 36, 0, undefined, { x1: 0, y1: 36, x2: 0, y2: 69 }),
      { x1: 0, y1: 36, x2: 33, y2: 36 });
check("a typed Y2 beats the remembered length",
      R(0, 36, undefined, 50, across), { x1: 0, y1: 36, x2: 0, y2: 50 });

console.log("\nand what the position is called");
check("across", runOf({ x1: 0, y1: 20, x2: 33, y2: 20 }), "across");
check("up and downstage", runOf({ x1: 6, y1: 10, x2: 6, y2: 30 }), "up-and-downstage");
check("a point", runOf({ x1: 6, y1: 10, x2: 6, y2: 10 }), "a point");
check("raked", runOf({ x1: 0, y1: 10, x2: 20, y2: 30 }), "raked");

console.log("\nthe toolbar keeps its controls where they can be reached");
// 🔴 Jerry, 2026.09.25: "I can't see a tick box for the rulers." It was in the
// DOM and 20px past the right edge of a 1024px window, because it had been
// appended to a row that was already 1108px wide. Present, unreachable, and
// indistinguishable from the feature not working at all.
//
// ⚠ There is no DOM in these tests, so this asserts the MARKUP instead: the
// print toggle has to live in the same bar as the display toggles, which is
// the short row. A layout bug cannot be caught here, but putting a control
// back on the full row can be.
{
  const fs = await import("node:fs");
  const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const bars = html.split(/<div class="bar">/).slice(1);
  const barWith = (id: string) => bars.findIndex(b => b.includes(`id="${id}"`));
  check("the rulers toggle is in the markup", /id="rulers"/.test(html), true);
  check("...in the same bar as the display toggles",
        barWith("rulers") === barWith("labels") && barWith("labels") >= 0, true);
  check("...and NOT in the bar with Export and the scale menu",
        barWith("rulers") === barWith("export"), false);
  check("it says it only affects the print", /rulers\s*<span class="print-only"/.test(html), true);
}

console.log("\nunits are never hand-formatted outside the formatters");
// 🔴 fmtFc existed, was tested, and was called by NOTHING. The inspector
// printed `${c.footcandles} fc` directly, so a metric plot showed throws and
// pools in metres and the level beside them in footcandles. The PDF was right
// and the screen was wrong, which is the harder way round to notice.
//
// ⚠ So the assertion is not "the inspector imports fmtFc" — that passes the
// moment somebody imports it and keeps the old string. It is that NO app
// source hand-writes a unit onto a number. fmtFt and fmtFc are the only two
// places allowed to, and they live in geometry.ts.
{
  const fs = await import("node:fs");
  const path = await import("node:path");
  const dir = new URL("./", import.meta.url).pathname;
  const exempt = new Set(["geometry.ts", "feet.ts", "geometry.test.ts", "store.test.ts"]);
  const offenders: string[] = [];
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith(".ts") && !exempt.has(f))) {
    const src = fs.readFileSync(path.join(dir, f), "utf8");
    for (const [i, line] of src.split("\n").entries()) {
      if (line.trimStart().startsWith("//") || line.trimStart().startsWith("*")) continue;
      // a value interpolated straight onto a unit: `${x} fc`, `${x} lx`, `${x} m`
      if (/\}\s*(fc|lx)\b/.test(line)) offenders.push(`${f}:${i + 1}`);
    }
  }
  check("no source pastes a unit onto a number", offenders, []);
  const insp = fs.readFileSync(path.join(dir, "inspector.ts"), "utf8");
  check("the inspector formats levels through fmtFc", /fmtFc\(/.test(insp), true);
}

console.log("\nthe splitter leaves the drawing the width it promises");
// 🔴 Found by Copilot's review of the first outside contribution, after a
// human review that missed it. The clamp subtracted CANVAS_MIN from the window
// but never the splitter's own 6px column, so dragging the panel as wide as it
// would go left the canvas 234px against an advertised 240.
//
// ⚠ It was in my own test output — clamped to 1260 in a 1500px window, and
// 1500 − 1260 − 6 is 234 — and I read past it. A number that is nearly right
// is the easiest kind to miss.
//
// There is no DOM here, so this pins the ARITHMETIC that the clamp has to
// satisfy. It is the rule, stated once, that the implementation must match.
{
  const ASIDE_MIN = 280, CANVAS_MIN = 240, SPLITTER_W = 6;
  const clamp = (w: number, room: number) =>
    Math.round(Math.max(ASIDE_MIN, Math.min(w, room - CANVAS_MIN - SPLITTER_W)));
  const canvasLeft = (aside: number, room: number) => room - aside - SPLITTER_W;

  check("dragged as wide as it goes, the drawing keeps its minimum",
        canvasLeft(clamp(Infinity, 1500), 1500), CANVAS_MIN);
  check("...and that is not 234", canvasLeft(clamp(Infinity, 1500), 1500) === 234, false);
  check("a width in the middle is left alone", clamp(600, 1500), 600);
  check("crushed the other way it stops at the panel minimum",
        clamp(0, 1500), ASIDE_MIN);
  // On a narrow window the two minimums cannot both be met. The PANEL wins,
  // because a panel below 280 is unusable while a squeezed drawing still
  // scrolls — but it must be a deliberate choice, not an accident of Math.min.
  check("on a window too narrow for both, the panel minimum wins",
        clamp(999, 400), ASIDE_MIN);
  const fs2 = await import("node:fs");
  const path2 = await import("node:path");
  const src = fs2.readFileSync(
    path2.join(new URL("./", import.meta.url).pathname, "main.ts"), "utf8");
  check("the clamp really does subtract the splitter",
        /room - CANVAS_MIN - SPLITTER_W/.test(src), true);
  check("...and re-clamps when the window changes",
        /addEventListener\("resize"/.test(src), true);
  check("the separator is keyboard-operable",
        /bar\.tabIndex = 0/.test(src) && /"keydown"/.test(src), true);
  check("...and reports its value to a screen reader",
        /aria-valuenow/.test(src), true);
}

// ⭐ "If someone selects a light and does nothing to it, should the plot be
// considered changed?" — Jerry, 2026.09.29. No. And nor should an edit that
// writes back the value already there. `dirty` means THE DOCUMENT DIFFERS FROM
// DISK, not "the user touched something". docs/DECISIONS.md.
console.log("\ndoing nothing is not a change");
s = new Store(base());
s.select(0);
check("selecting a light leaves it clean", s.dirty, false);
check("...and adds no undo step", s.canUndo, false);
s.select(null);
check("deselecting too", s.dirty, false);

s.begin(null); s.update(0, { x: 5 });        // x is already 5
check("writing back the same value is not an edit", s.dirty, false);
check("...and pushes no dead undo step", s.canUndo, false);

s.begin(null); s.update(0, { color: undefined });   // was never set
check("clearing an already-empty field is not an edit", s.dirty, false);

// ⚠ A drag that ends where it started. interact.ts coalesces on a key, so this
// is the path a real mouse takes, not a synthetic one.
s.begin("drag:0"); s.update(0, { x: 5, y: 20 });
check("a drag that lands where it started", s.dirty, false);
s.commit();

console.log("\na real edit still counts");
s.begin(null); s.update(0, { x: 9 });
check("dirty", s.dirty, true);
check("and undoable", s.canUndo, true);

console.log("\nundo back to the saved state goes clean again");
s = new Store(base());
s.begin(null); s.update(0, { x: 7 });
check("edited", s.dirty, true);
s.undo();
check("undone to what was loaded", s.dirty, false);
s.redo();
check("redone", s.dirty, true);

s.markSaved();
check("saved here", s.dirty, false);
s.undo();
check("stepping BACK from the save point is dirty", s.dirty, true);
s.redo();
check("...and returning to it is clean", s.dirty, false);

// 🔴 The one that made `_redo = []` necessary instead of `.length = 0`.
console.log("\na no-op does not eat the redo stack");
s = new Store(base());
s.begin(null); s.update(0, { x: 7 });
s.undo();
check("there is something to redo", s.canRedo, true);
s.begin(null); s.update(0, { x: 5 });        // tabbing out of an unchanged field
check("...and a no-op leaves it there", s.canRedo, true);
s.redo();
check("redo still works", s.plot.instruments[0]!.x, 7);


// ------------------------------------------- a pipe by its length and angle
// 🔴 The arithmetic a designer should not have to do. A position is two
// endpoints, so an angled pipe was always possible — by working out the far end
// yourself, and again every time you nudged the angle. #62, raised by a tester
// hanging truss towers at a slight angle to follow a warehouse wall.
console.log("\na pipe can be given a length and an angle");

const R4 = (n: number) => Math.round(n * 1e4) / 1e4;
const ends = (o: { x1: number; y1: number; x2: number; y2: number }) =>
  ({ x1: R4(o.x1), y1: R4(o.y1), x2: R4(o.x2), y2: R4(o.y2) });

check("0 degrees runs across", ends(endsFromLengthAngle(0, 10, 20, 0)),
      { x1: 0, y1: 10, x2: 20, y2: 10 });
check("...and runOf agrees", runOf(endsFromLengthAngle(0, 10, 20, 0)), "across");
check("90 degrees runs up and downstage", ends(endsFromLengthAngle(5, 0, 20, 90)),
      { x1: 5, y1: 0, x2: 5, y2: 20 });
// ⚠ cos(90°) is 6e-17, not 0. Without rounding, x2 differs from x1 by a
// hair and runOf calls a pipe up the deck "raked".
check("...and is not called raked by a rounding error",
      runOf(endsFromLengthAngle(5, 0, 20, 90)), "up-and-downstage");
check("a slight rake", ends(endsFromLengthAngle(0, 0, 20, 12)),
      { x1: 0, y1: 0, x2: R4(20 * Math.cos(12 * Math.PI / 180)),
        y2: R4(20 * Math.sin(12 * Math.PI / 180)) });

// ⭐ The pair must round-trip, because the panel shows both and writes both.
for (const [len, ang] of [[20, 0], [20, 90], [20, 12], [33, -35], [12.5, 180]]) {
  const e = endsFromLengthAngle(4, 7, len!, ang!);
  check(`round-trips at ${len}' / ${ang}deg`,
        [R4(lengthOf(e)), R4(((angleOf(e) - ang! + 540) % 360) - 180)], [R4(len!), 0]);
}

// ⚠ The near end does NOT move. Turning a pipe swings the far end about the
// end you first placed — the one you measured off the wall.
const _turned = endsFromLengthAngle(4, 7, 20, 40);
check("the near end stays put", [_turned.x1, _turned.y1], [4, 7]);

check("a position with no length has no angle, not NaN",
      angleOf({ x1: 3, y1: 3, x2: 3, y2: 3 }), 0);
check("length of a point is zero", lengthOf({ x1: 3, y1: 3, x2: 3, y2: 3 }), 0);
check("a 3-4-5 pipe is 5 long", lengthOf({ x1: 0, y1: 0, x2: 3, y2: 4 }), 5);


// ------------------------------------------------ two positions, one name
// 🔴 A position's name is the JOIN KEY. Units say which position they are on by
// name, so two positions called the same thing share their rig, merge in the
// schedule and move each other's trim. Jerry, 2026.09.30: "I can see that
// happening. Perhaps the position is a V for instance."
console.log("\na duplicate position name is caught");

const pos = (name: string) => ({ name });
check("no clash on distinct names",
      [...duplicateNames([pos("GRID B"), pos("GRID C")])], []);
check("a repeat is caught",
      [...duplicateNames([pos("V"), pos("GRID C"), pos("V")])], ["v"]);
// ⚠ Compared the way the joins compare: trimmed and lower-cased. "Grid C" and
// "GRID C " are the same position to every reader of the plot.
check("case does not save you",
      [...duplicateNames([pos("Grid C"), pos("GRID C")])], ["grid c"]);
check("nor does a trailing space",
      [...duplicateNames([pos("GRID C"), pos("GRID C ")])], ["grid c"]);
check("three of a kind is still one clash",
      [...duplicateNames([pos("V"), pos("V"), pos("V")])], ["v"]);
// An unnamed position has its own problem; it is not this one, and reporting
// every blank as a clash with every other blank would bury the real ones.
check("blank names are not a clash",
      [...duplicateNames([pos(""), pos(""), pos("GRID C")])], []);

console.log("\ntwo units with the same number on one position");
const u = (position: string, unit: number) => ({ position, unit });
// ⭐ RP-2 numbers units PER POSITION, so unit 1 on two pipes is correct.
check("the same number on two different pipes is fine",
      duplicateUnits([u("GRID B", 1), u("GRID C", 1)], "GRID C"), []);
check("...but twice on one pipe is not",
      duplicateUnits([u("GRID C", 1), u("GRID C", 1)], "GRID C"), [1]);
check("reported in order", duplicateUnits(
      [u("GRID C", 3), u("GRID C", 1), u("GRID C", 3), u("GRID C", 1)], "GRID C"), [1, 3]);
check("matched the way the joins match",
      duplicateUnits([u("grid c", 2), u("GRID C ", 2)], "GRID C"), [2]);
check("a unit with no number is not a duplicate",
      duplicateUnits([{ position: "GRID C" }, { position: "GRID C" }], "GRID C"), []);


// ------------------------------------------- sharing a name is allowed, not wrong
// ⭐ Jerry, 2026.09.30: "let the user name the position... Then if its the same
// name, say there is already a position with that name - let them use the same
// name if they want." A V or an L is ONE position made of two straight
// segments, and sharing the name is how you say so.
console.log("\nsharing a name is offered, not refused");

const _one = sharedNameMessage("V", 1);
check("it names the position", _one.includes('"V"'), true);
check("...and says how many already have it", _one.includes("another position"), true);
check("two others are counted", sharedNameMessage("V", 2).includes("2 other positions"), true);
// ⚠ The dialog must say what sharing MEANS, because that is the decision being
// made. "Are you sure?" would ask the reader to work it out themselves.
check("it explains the numbering", _one.includes("one run of unit numbers"), true);
check("...and that the schedule merges them", _one.includes("schedule"), true);
check("...and names the case it is for", /V or an L/.test(_one), true);
// 🔴 It must not read as a refusal. This is a legitimate thing to want.
check("it does not warn against it", /cannot|must not|error|invalid/i.test(_one), false);
check("it ends with the question", _one.trim().endsWith("Use the same name?"), true);


// ------------------------------------- the SUGGESTED name is one nobody is using
// 🔴 The old button invented `Electric ${positions.length + 1}`, which is one
// delete away from a collision: the demo ships seven positions, one called
// "Electric 7", so deleting any of them and pressing add produced a second
// "Electric 7" with no prompt and no warning. Reproduced in the app.
//
// ⚠ This is the SUGGESTION only. A clash the user types deliberately is still
// allowed — see sharedNameMessage — because a V is a real thing to want.
console.log("\nthe suggested position name is free");

const P = (...names: string[]) => names.map(n => ({ name: n }));
check("an empty plot starts at 1", nextPositionName(P()), "Electric 1");
check("counts from the number of positions",
      nextPositionName(P("a", "b", "c")), "Electric 4");
check("skips a name already taken",
      nextPositionName(P("Cat 1", "GRID C", "GRID D", "HR Boom", "HL Boom", "Electric 7")),
      "Electric 8");
check("...and keeps skipping",
      nextPositionName(P("a", "b", "Electric 3", "Electric 4", "Electric 5")),
      "Electric 6");
check("case-insensitively, the way the joins compare",
      nextPositionName(P("a", "b", "electric 3")), "Electric 4");

// ⭐ The invariant, not the examples: what the button suggests is never what
// duplicateNames flags.
let _grow = P("Cat 1", "GRID C", "GRID D", "HR Boom", "HL Boom", "Electric 7");
let _clean = true;
for (let i = 0; i < 12; i++) {
  _grow = [..._grow, { name: nextPositionName(_grow) }];
  if (duplicateNames(_grow).size) _clean = false;
}
check("twelve in a row never suggests a duplicate", _clean, true);

// ---------------------------------------------------------------- renumber
// 🔴 Jerry, 2026.09.30: "you can't just renumber the units […] you can allow the
// user to do it, but doing automatically is bad." So two things are tested: the
// dialog SAYS what a shared name does to the order, and nothing in the UI tells
// the reader to press the button.
const _rn = sharedNameRenumberNote("Cove", 2);
check("names the position", _rn.includes('"Cove"'), true);
check("counts the legs", _rn.includes("2 positions"), true);
check("says which leg set the order", _rn.includes("FIRST"), true);
check("says they alternate", _rn.includes("alternate"), true);
check("sends the reader to the moves, not to Apply",
      _rn.includes("check the moves"), true);
// ⚠ It must not read as a refusal — the reader is allowed to do this.
check("does not refuse", /cannot|refus|not allowed/i.test(_rn), false);

// ⭐ THE REAL REGRESSION, and the reason this block exists. The duplicate-unit
// note used to end "Renumber fixes it across every segment of the name", which
// pointed the reader at a button that rewrites every number on the run. It now
// points at the one number that is wrong. Asserted against the SOURCE, because
// the note is built inline in a DOM-rendering function.
const _fsRn = await import("node:fs");
const _srcRaw = _fsRn.readFileSync(new URL("./positions.ts", import.meta.url), "utf8");
// ⚠ COMMENTS STRIPPED FIRST. The assertion is about what reaches the reader, and
// the comments explaining this very change mention the old wording — a test that
// failed on its own explanation would push the explanation out of the file.
const _src = _srcRaw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
check("no note tells the reader to press renumber",
      /press renumber|Renumber fixes/.test(_src), false);
check("the duplicate-unit note offers the by-hand fix instead",
      _src.includes("Give one of each pair a free number"), true);
// And the button itself is still there — this was never about removing it.
check("the renumber button survives", _src.includes('textContent = "renumber"'), true);

// ------------------------------------------------- every suite actually runs
// 🔴 `test:all` LISTS THE SUITES BY HAND, so a new test file runs on the author's
// machine and never in CI — which is the same failure `verify_suites.py` exists
// for on the Python side, where `for t in test_*.py` at least globs. Nothing
// checked the web side until `sequence.test.ts` was added and this was noticed.
//
// ⚠ Asserted from package.json, not from a list typed here. A list typed here
// would be a THIRD place suites live.
{
  const fsS = await import("node:fs");
  const pkg = JSON.parse(fsS.readFileSync(
    new URL("../package.json", import.meta.url), "utf8")) as
    { scripts: Record<string, string> };
  const scripts = Object.values(pkg.scripts).join(" ");
  const dirS = new URL("./", import.meta.url).pathname;
  const suites = fsS.readdirSync(dirS).filter(f => f.endsWith(".test.ts")).sort();
  check("there is more than one suite to check", suites.length > 1, true);
  const unrun = suites.filter(f => !scripts.includes(f));
  check("every *.test.ts is reachable from a script", unrun, []);
  // And reachable from test:all specifically — a script nothing calls is not run.
  const all = pkg.scripts["test:all"] ?? "";
  const called = [...all.matchAll(/npm (?:run )?([\w:]+)/g)].map(m => m[1]!);
  const reached = ["test:all", ...called]
    .map(n => pkg.scripts[n] ?? "").join(" ");
  check("...and from test:all", suites.filter(f => !reached.includes(f)), []);
}

// ------------------------------------------- labels must not eat the click
// 🔴 A UNIT'S OWN NUMBER USED TO SWALLOW THE CLICK AIMED AT THE UNIT. §6.14.2
// puts the number INSIDE the body, so the `text` sits exactly over the body
// circle — and `interact.ts` resolves a click with `closest("[data-index]")`,
// which the annotation layer is not inside. No hit means `store.select(null)`,
// so clicking a light's number DESELECTED it.
//
// ⚠ Found only by opening the app — every suite passed throughout. It is
// pinned here because the symptom is invisible in a diff and easy to reintroduce
// by rebuilding the label group.
{
  const fsA = await import("node:fs");
  const r = fsA.readFileSync(new URL("./render.ts", import.meta.url), "utf8");
  const m = /el\("g", \{ class: "annot"([^}]*)\}\)/.exec(r);
  check("the annotation group is still created here", !!m, true);
  check("...and is not clickable",
        (m?.[1] ?? "").includes('"pointer-events": "none"'), true);
}

if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
