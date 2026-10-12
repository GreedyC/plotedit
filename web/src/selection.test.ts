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
import { selectionOverride, mountAngle, type RenderOptions } from "./render.js";
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


// ---------------------------------------------------------------- #113
// A strip is hung at two points and does not turn. Pure, so it is tested by
// BEHAVIOUR here; test_two_point.py checks the Python agrees, because the screen
// and the paper disagreeing about which way a unit points is a bug this project
// has already shipped once.
console.log("\n🔴 #113 — a two-point fixture lies along its pipe");
{
  const across = { name: "CYC ELECTRIC", type: "electric" as const,
                   x1: -14, y1: 18, x2: 14, y2: 18, trim: 14 };
  const upDown = { name: "UP-DOWN", type: "electric" as const,
                   x1: 0, y1: 0, x2: 0, y2: 20, trim: 14 };
  const plot = { formatVersion: 1, show: "T", room: { width: 34, depth: 24 },
                 positions: [across, upDown], instruments: [] } as unknown as Plot;
  const strip = (pos: string, aim?: [number, number]) => ({
    unit: 1, position: pos, type: "Chroma-Q Color Force II Plus 72",
    x: 0, y: 18, trim: 14,
    ...(aim ? { focusX: aim[0], focusY: aim[1] } : {}),
  }) as unknown as Instrument;
  const o = (keys: string[]): RenderOptions =>
    ({ layers: vis(), twoPoint: new Set(keys) });
  const TWO = ["Chroma-Q Color Force II Plus 72"];

  check("a unit that can pan is left alone",
        mountAngle({ unit: 1, position: "CYC ELECTRIC", type: "S4 26",
                     x: 0, y: 18 } as unknown as Instrument, plot, o(TWO)), undefined);
  check("a strip on a cross-stage pipe lies across stage",
        mountAngle(strip("CYC ELECTRIC"), plot, o(TWO)), 0);
  check("a strip on an up-and-downstage pipe lies up and down",
        mountAngle(strip("UP-DOWN"), plot, o(TWO)), 90);
  // 🔴 The bug itself: these differ only in where they are aimed.
  for (const aim of [[14, 17], [-14, 17], [0, 30]] as [number, number][])
    check(`aimed at ${aim} — still across stage`,
          mountAngle(strip("CYC ELECTRIC", aim), plot, o(TWO)), 0);
  // ⚠ A ground row has no pipe to read. Across stage is where they go — a
  // documented limitation, not a measurement.
  check("no position at all", mountAngle(strip(""), plot, o(TWO)), 0);
  check("a position that is not in the plot", mountAngle(strip("GONE"), plot, o(TWO)), 0);
  // ⚠ And nothing is forced when the server did not say it was two-point.
  check("not flagged — nothing forced", mountAngle(strip("CYC ELECTRIC"), plot, o([])), undefined);
}

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
