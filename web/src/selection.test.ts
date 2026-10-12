/** Run: cd web && npm run test:selection
 *
 * #109: clicking a unit shows its pool and focus point even with those layers
 * off. A pure predicate, so it can be tested without a DOM — which is the reason
 * it was pulled out of render() rather than written inline three times.
 *
 * 🔴 THE RULE THAT IS EASY TO GET BACKWARDS, and which I did get backwards once
 * on the issue before writing this: it is the OVERRIDE that is gated on `units`,
 * not the layer. `(vis.pools || sel) && vis.units` reads almost the same and is
 * wrong — it would switch the pools layer off whenever the symbols were off,
 * which is a documented, deliberate way to read a rig.
 */
import { selectionOverride, positionAngle, takesThePipeAngle, PLUMB_DEG, UPSTAGE,
         type RenderOptions } from "./render.js";
import type { Plot, Instrument } from "./plot.js";
import { LAYERS, type LayerId } from "./layers.js";
import type { Visibility } from "./layers.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(56)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

/** Every layer on, then switch off whatever the case needs. */
const vis = (off: LayerId[] = []): Visibility => {
  const v = {} as Visibility;
  for (const l of LAYERS) v[l.id] = !off.includes(l.id);
  return v;
};

console.log("the selected unit, and only the selected unit");
check("the one you clicked", selectionOverride(vis(), 3, 3), true);
check("not its neighbour", selectionOverride(vis(), 3, 4), false);
check("nothing selected", selectionOverride(vis(), null, 3), false);
check("selection undefined", selectionOverride(vis(), undefined, 3), false);
// ⚠ 0 is a real index and falsy. A `!selected` guard would break unit one.
check("index 0 is a selection, not an absence",
      selectionOverride(vis(), 0, 0), true);

console.log("\n🔴 the override needs a symbol to belong to");
check("units off — a Schedule click shows nothing on the plan",
      selectionOverride(vis(["units"]), 3, 3), false);
check("...even with pools and focus also off",
      selectionOverride(vis(["units", "pools", "focus"]), 3, 3), false);
check("units on — the override applies",
      selectionOverride(vis(["pools", "focus"]), 3, 3), true);

console.log("\n⚠ the override does not care about pools or focus themselves");
// It is OR-ed with them at the call site; its own answer is about the selection.
check("pools off", selectionOverride(vis(["pools"]), 2, 2), true);
check("focus off", selectionOverride(vis(["focus"]), 2, 2), true);
check("both off", selectionOverride(vis(["pools", "focus"]), 2, 2), true);

console.log("\n🔴 the gates at the call site read the right way round");
// Source check, because the mistake is one character and silent: the LAYER must
// not be suppressed when units are off.
const src = await import("node:fs")
  .then(fs => fs.readFileSync(new URL("./render.ts", import.meta.url), "utf8"));
check("the pool gate ORs the override in",
      /\(vis\.pools \|\| selShows\) && hasFocus && c\?\.pool\b/.test(src), true);
check("the pool-note gate too",
      /\(vis\.pools \|\| selShows\) && hasFocus && c\?\.pool_note/.test(src), true);
check("the focus gate too",
      /\(vis\.focus \|\| selShows\) && hasFocus/.test(src), true);
check("🔴 and NOTHING ands vis.units onto a whole layer gate",
      /\(vis\.(pools|focus) \|\| [A-Za-z]+\) && vis\.units/.test(src), false);

console.log("\n⚠ a selected POSITION does not do this — Jerry, 2026.10.12");
// Forty pools at once on a big electric is a smear, not a highlight. The
// predicate takes an instrument index and knows nothing about positions, which
// is how that decision is enforced rather than remembered.
check("it takes no position argument", selectionOverride.length, 3);


// ------------------------------------------------------------ #113 and #116
// When a unit is drawn along its pipe instead of toward its focus. Two reasons,
// one rule. Pure, so it is tested by BEHAVIOUR; test_two_point.py checks the
// Python agrees, because the screen and the paper disagreeing about which way a
// unit points is a bug this project has already shipped once.
console.log("\n\u{1F534} #113 and #116 — when a unit is drawn along its pipe");
{
  const across = { name: "CYC ELECTRIC", type: "electric" as const,
                   x1: -14, y1: 18, x2: 14, y2: 18, trim: 14 };
  const upDown = { name: "UP-DOWN", type: "electric" as const,
                   x1: 0, y1: 0, x2: 0, y2: 20, trim: 14 };
  const plot = { formatVersion: 1, show: "T", room: { width: 34, depth: 24 },
                 positions: [across, upDown], instruments: [] } as unknown as Plot;
  const unit = (type: string, pos: string) =>
    ({ unit: 1, position: pos, type, x: 0, y: 18, trim: 14 }) as unknown as Instrument;
  const o = (keys: string[]): RenderOptions => ({ layers: vis(), twoPoint: new Set(keys) });
  const TWO = ["Chroma-Q Color Force II Plus 72"];
  const strip = (p: string) => unit("Chroma-Q Color Force II Plus 72", p);
  const ers = (p: string) => unit("S4 26", p);

  // ⭐ The unit FACES UPSTAGE, so the pipe's run is turned a half turn. 180, not 0.
  check("a cross-stage pipe faces upstage", positionAngle(strip("CYC ELECTRIC"), plot), 180);
  check("an up-and-downstage pipe", positionAngle(strip("UP-DOWN"), plot), 90);
  // \u{1F534} THE SAME PIPE TYPED BACKWARDS MUST GIVE THE SAME ANSWER. Taking the
  // facing from the run's direction flipped Big House's catwalks downstage while
  // leaving its electrics upstage, because the catwalks were entered right to left.
  {
    const rev = { ...plot, positions: [{ name: "CYC ELECTRIC", type: "electric" as const,
                  x1: 14, y1: 18, x2: -14, y2: 18, trim: 14 }] } as unknown as Plot;
    check("...and the same pipe entered backwards agrees",
          positionAngle(strip("CYC ELECTRIC"), rev), 180);
  }
  check("no position — across stage, upstage", positionAngle(strip(""), plot), 180);
  check("a position not in the plot", positionAngle(strip("GONE"), plot), 180);
  check("UPSTAGE is the half turn", UPSTAGE, 180);

  for (const el of [undefined, 5, 45, 89])
    check(`\u{1F534} #113 strip at elevation ${el} — the pipe`,
          takesThePipeAngle(strip("CYC ELECTRIC"), o(TWO), el), true);

  check("\u{1F534} #116 an ERS focused normally keeps its aim",
        takesThePipeAngle(ers("CYC ELECTRIC"), o(TWO), 30), false);
  check("   ...at 87.9\u00b0, still its aim",
        takesThePipeAngle(ers("CYC ELECTRIC"), o(TWO), 87.9), false);
  check("   ...at 88.0\u00b0, the pipe",
        takesThePipeAngle(ers("CYC ELECTRIC"), o(TWO), 88.0), true);
  check("   ...at 90\u00b0, the pipe",
        takesThePipeAngle(ers("CYC ELECTRIC"), o(TWO), 90), true);
  // \u26a0 An unfocused unit has no elevation at all. Nothing may be forced on that.
  check("   ...no elevation computed — left alone",
        takesThePipeAngle(ers("CYC ELECTRIC"), o(TWO), undefined), false);
  // \u26a0 And the threshold must match the Python, or the two drawings disagree.
  check("the threshold is 88", PLUMB_DEG, 88.0);
}

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
