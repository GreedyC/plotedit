/** Run: cd web && npm test */
import { toScreen, toPlot, len, fitView, fohExtent, fmtFt, svgTransform, notationAnchor, symbolRadius,
         symbolTransform, lensDirection, fmtFc, setUnitSystem, unitSystem,
         M_PER_FOOT, placeBase, type View } from "./geometry.js";
import { parseFeet } from "./feet.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(44)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}
const round = (p: { x: number; y: number }) => ({ x: +p.x.toFixed(4), y: +p.y.toFixed(4) });

const v: View = { scale: 10, panX: 0, panY: 0, width: 400, height: 300 };

console.log("the y axis flips");
check("plot origin sits at the bottom-left", round(toScreen({ x: 0, y: 0 }, v)), { x: 0, y: 300 });
check("upstage is UP the screen", round(toScreen({ x: 0, y: 10 }, v)), { x: 0, y: 200 });
check("stage right is right", round(toScreen({ x: 10, y: 0 }, v)), { x: 100, y: 300 });

console.log("\nround trip");
for (const p of [{ x: 0, y: 0 }, { x: 16.5, y: 20 }, { x: -3, y: 41.25 }]) {
  check(`(${p.x}, ${p.y}) survives there and back`, round(toPlot(toScreen(p, v), v)), p);
}

console.log("\nlengths carry no offset and no flip");
check("10 feet at 10 px/ft", len(10, v), 100);
check("panning does not change a length", len(10, { ...v, panX: 99, panY: -7 }), 100);

console.log("\nfitView");
const f = fitView(33, 38, 800, 600);      // the test room
check("scale fits the tall axis", +f.scale.toFixed(4), +(600 / 44).toFixed(4));
const c1 = toScreen({ x: 0, y: 0 }, f), c2 = toScreen({ x: 33, y: 38 }, f);
check("room is inside the surface", c1.x > 0 && c2.x < 800 && c2.y > 0 && c1.y < 600, true);
check("room is centered horizontally", +(c1.x - (800 - (c2.x - c1.x)) / 2).toFixed(2), 0);

console.log("\nsvgTransform puts the origin where toScreen does");
const t = svgTransform(v);
check("has scale with a negative y", t.includes("scale(10 -10)"), true);

console.log("\nfmtFt");
check("13.75", fmtFt(13.75), `13'-9"`);
check("12 inches rolls over", fmtFt(4.9999), `5'-0"`);
check("null is not zero", fmtFt(null), "—");

console.log();

// ⭐ CORRECTED 2026.09.24. These used to assert that front of house sat at
// NEGATIVE y and that the canvas had to be extended downstage to reach it. That
// was a wrong model, and Jerry named it: "the FOH catwalk would need to be
// inside the room."
//
// The room is the WHOLE room. The test room is 33' x 38' with its plaster line at
// y = 10, so the house is y 0–10 and the stage 10–38 — one rectangle holding
// both. An FOH position belongs INSIDE it, and a view fitted to the room shows
// it without any extension at all.
{
  const v = fitView(33, 38, 600, 900, 3);
  const cat = toScreen({ x: 16, y: 4 }, v);      // a catwalk over the house
  const wall = toScreen({ x: 16, y: 38 }, v);    // the back wall
  check("an FOH position inside the room is on the canvas",
        cat.y > 0 && cat.y < v.height, true);
  check("...and so is the back wall", wall.y > 0 && wall.y < v.height, true);
  check("the house is still BELOW the stage on screen", cat.y > wall.y, true);

  // The extension existed only to reach outside the room. Nothing is outside it.
  check("no canvas extension is needed any more",
        fohExtent([{ y1: 4, y2: 4, width: 3, type: "catwalk" }]), 0);
}


// ⚠ The verdict goes LAST. It used to sit in the middle of the file, so
// anything appended after it ran WITHOUT affecting the exit code — the suite
// could print failures and still exit 0. The same defect was found in two of the
// Python suites on 2026.09.23; verify_suites.py checks those, and did not cover
// these.
console.log("\nnotation follows the instrument, not the page");
// ⭐ Colour in FRONT of the lens, channel BEHIND — for every way a unit can aim.
// The screen drew both at fixed page offsets until 2026.09.24, which put the
// channel number inside the beam of anything focused downstage.
// d > 0 is behind, d < 0 is in front.
// 0° points the instrument toward -y (downstage) — symbols.draw()'s convention,
// where local -a is the lens. Getting this backwards is exactly the bug.
for (const [name, deg, front] of [
  ["aimed downstage", 0, { x: 0, y: -1 }],
  ["aimed upstage", 180, { x: 0, y: 1 }],
  ["aimed stage right", 90, { x: 1, y: 0 }],
  ["aimed stage left", 270, { x: -1, y: 0 }],
] as [string, number, { x: number; y: number }][]) {
  check(`${name}: colour at the lens`, round(notationAnchor(0, 0, deg, -1)), round(front));
  check(`${name}: channel behind`, round(notationAnchor(0, 0, deg, 1)),
        round({ x: -front.x, y: -front.y }));
}
check("off-axis follows the symbol", round(notationAnchor(10, 20, 45, -1)),
      { x: 10.7071, y: 19.2929 });

console.log("\nnotation clears the symbol by the symbol's own size");
// The mirror of symbols.py radius(). An ERS reaches ~1 ft past its yoke; a
// striplight reaches six.
check("nothing", symbolRadius(undefined), 0);
check("a body", +symbolRadius([{ k: "poly", pts: [[0.8, 0.3], [-0.9, 0.3]], closed: true }]).toFixed(4), 0.9487);
check("a circle counts its radius", symbolRadius([{ k: "circle", c: [1, 0], r: 0.5 }]), 1.5);
check("an unknown primitive is skipped, not unpacked", symbolRadius([{ k: "arc", pts: [[9, 9]] }]), 0);
check("the farthest wins", symbolRadius([{ k: "line", a: [0, 0], b: [3, 4] }, { k: "circle", c: [0, 0], r: 1 }]), 5);

console.log("\nthe canvas makes room for the boom elevations");
// ⭐ RP-2 §6.12 elevations sit off the stage-left edge at NEGATIVE x. Fit to the
// room alone and they are simply off the left of the canvas — no warning, just
// a boom's units missing from the drawing, which is worse now that plan skips
// them on purpose.
{
  const v2 = fitView(33, 38, 800, 600, 3, 0, 13);
  check("the leftmost elevation is on the canvas", toScreen({ x: -13, y: 0 }, v2).x >= 0, true);
  check("the room's stage-left wall still is", toScreen({ x: 0, y: 0 }, v2).x > 0, true);
  check("and its stage-right wall", toScreen({ x: 33, y: 0 }, v2).x <= 800, true);
  const v0 = fitView(33, 38, 800, 600, 3, 0, 0);
  check("no booms, no extra space", +v0.panX.toFixed(4), +(-(800 / v0.scale - 33) / 2).toFixed(4));
}

console.log("\nan instrument points where it is aimed");
// 🔴 Jerry, 2026.09.24: "the instruments on the US DS electric are pointing the
// wrong way when they are focused." render.ts wrote rotate(-pan), which agrees
// with symbols.draw() at 0 and 180 — where sin is zero — and MIRRORS it at ±90.
//
// ⚠ This checks where the LENS lands after SVG's own rotation matrix, not which
// angle we chose to write. Asserting the angle would just restate the code; the
// question is which way the light ends up facing.
//
// The convention is symbols.draw()'s: 0 aims downstage (-y), 90 stage right.
for (const [deg, want] of [
  [0, { x: 0, y: -1 }], [90, { x: 1, y: 0 }],
  [180, { x: 0, y: 1 }], [270, { x: -1, y: 0 }],
] as [number, { x: number; y: number }][]) {
  check(`aimed at ${deg}deg the lens faces ${JSON.stringify(want)}`,
        round(lensDirection(deg)), round(want));
}
check("off-axis too", round(lensDirection(45)), { x: 0.7071, y: -0.7071 });

// And the transform render() actually writes carries that same angle, so the
// check above is about the drawing rather than about an unused function.
{
  const t = symbolTransform(5.5, 20, 90);
  check("the transform places the unit", t.startsWith("translate(5.5 20)"), true);
  const deg = Number(/rotate\(([-\d.]+)\)/.exec(t)![1]);
  check("...and rotates it the way the lens test assumes",
        round(lensDirection(deg)), { x: 1, y: 0 });
}

console.log("\nunits: the label changes, the stored value never does");
check("imperial is the default", unitSystem(), "imperial");
check("a plot that says nothing is imperial", (setUnitSystem(undefined), unitSystem()), "imperial");
check("'metric' switches it", (setUnitSystem("metric"), unitSystem()), "metric");
check("anything else does not", (setUnitSystem("Imperial"), unitSystem()), "imperial");

setUnitSystem("imperial");
check("feet print as feet", fmtFt(13.75), "13'-9\"");
check("footcandles print as fc", fmtFc(179), "179 fc");
setUnitSystem("metric");
check("the same value prints as metres", fmtFt(13.75), "4.19 m");
check("...from the SAME number of feet", fmtFt(13.75, "imperial"), "13'-9\"");
check("footcandles become lux", fmtFc(179), "1927 lx");

// 🔴 THE DOUBLE-CONVERSION TRAP. parseFeet returns FEET whatever was typed,
// and fmtFt takes FEET. Convert in either one as well and the number is
// multiplied twice — 3.28 is close enough to a plausible trim that nobody
// catches it by eye. This is the assertion that would fail.
console.log("\nwhat is typed comes back unchanged");
setUnitSystem("metric");
check("4.2 metres in, 4.20 m out", fmtFt(parseFeet("4.2") as number), "4.20 m");
check("...and it is really 13.78 feet inside",
      +(parseFeet("4.2") as number).toFixed(2), +(4.2 / M_PER_FOOT).toFixed(2));
check("'4.2m' is accepted too", fmtFt(parseFeet("4.2m") as number), "4.20 m");
// ⚠ Explicit imperial notation wins over the plot's system: somebody typing
// 5'6" means 5'6", and reading it as metres would be the worst answer available.
check("5'6\" is still five foot six on a metric plot",
      +(parseFeet("5'6\"") as number).toFixed(4), 5.5);
check("...which prints as its metric self", fmtFt(parseFeet("5'6\"") as number), "1.68 m");
setUnitSystem("imperial");
check("a bare number on an imperial plot is still feet", parseFeet("4.2"), 4.2);
check("nonsense is still nonsense", parseFeet("banana"), null);
check("empty is still empty", parseFeet(""), undefined);


// --------------------------------------------------- placing an imported plan
// 🔴 This arithmetic had no test because it had no home — it lived inside
// main.ts, next to the DOM, where nothing can import it. It is the sum that
// decides where a venue's own drawing sits on both the screen AND the print, so
// a drift here shows up as the paper disagreeing with the app.
console.log("");
console.log("an imported base plan goes where it is put");
const SQ: { layer: string; points: [number, number][] }[] =
  [{ layer: "WALL", points: [[0, 0], [10, 0], [10, 20], [0, 20]] }];

check("no transform hands back the very same array",
      placeBase(SQ, { x: 0, y: 0, rotate: 0 }) === SQ, true);
check("an offset moves every point",
      placeBase(SQ, { x: 3, y: 4, rotate: 0 })[0]!.points,
      [[3, 4], [13, 4], [13, 24], [3, 24]]);
check("the layer survives the move",
      placeBase(SQ, { x: 3, y: 4, rotate: 0 })[0]!.layer, "WALL");
check("a quarter turn is about the STAGE ORIGIN, not the drawing",
      placeBase(SQ, { x: 0, y: 0, rotate: 90 })[0]!.points.map(
        ([x, y]) => [+x.toFixed(4), +y.toFixed(4)]),
      [[0, 0], [0, 10], [-20, 10], [-20, 0]]);
check("...so x and y can put it back",
      placeBase(SQ, { x: 20, y: 0, rotate: 90 })[0]!.points.map(
        ([x, y]) => [+x.toFixed(4), +y.toFixed(4)]),
      [[20, 0], [20, 10], [0, 10], [0, 0]]);
// ⚠ Turn, THEN move — the other order puts the offset through the rotation and
// "x = 10'" stops meaning ten feet stage right.
check("the turn happens before the offset, so x is still feet",
      placeBase(SQ, { x: 10, y: 0, rotate: 180 })[0]!.points.map(
        ([x, y]) => [+x.toFixed(4), +y.toFixed(4)]),
      [[10, 0], [0, 0], [0, -20], [10, -20]]);
check("a full turn comes home", placeBase(SQ, { x: 0, y: 0, rotate: 360 })[0]!
        .points.map(([x, y]) => [Math.round(x), Math.round(y)]),
      [[0, 0], [10, 0], [10, 20], [0, 20]]);
check("the original is not mutated", SQ[0]!.points[1], [10, 0]);

if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
