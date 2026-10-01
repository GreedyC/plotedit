/** Run: cd web && npm run test:layers
 *
 * Two jobs, and the second is the one that would do real damage.
 *
 * 🔴 THE MIGRATION. Every plot saved before this release has no `layers` at
 * all. Read that as "nothing is visible" rather than "everything takes its
 * default" and the file opens as an empty room — the worst thing this change
 * could do, and a one-character mistake away at all times.
 *
 * 🔴 THE DRIFT GUARD. The chips in index.html are a second copy of
 * SCREEN_LAYERS. The lamp dropdown was a second copy of LAMP_MF and fell a
 * whole release behind it — twice — because nothing compared them. This reads
 * the markup and requires it to agree, so the next layer cannot reach one side
 * and not the other.
 */
import * as fs from "node:fs";
import { LAYERS, SCREEN_LAYERS, defaultLayers, visibilityOf, allVisible,
         type LayerId } from "./layers.js";
import { newPlot, type Plot } from "./plot.js";
import { Store } from "./store.js";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(50)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

const plain = (): Plot => ({
  formatVersion: 1, show: "T",
  room: { width: 30, depth: 40 },
  positions: [], instruments: [],
});

console.log("the set itself");
check("eight layers", LAYERS.length, 8);
check("ids are unique", new Set(LAYERS.map(l => l.id)).size, 8);
check("draw order, bottom to top", LAYERS.map(l => l.id),
      ["base", "pools", "positions", "focus", "units", "labels",
       "dimensions", "notes"]);
check("six of them draw on screen", SCREEN_LAYERS.map(l => l.id),
      ["base", "pools", "positions", "focus", "units", "labels"]);
check("every layer has a label and a tooltip",
      LAYERS.filter(l => !l.label || !l.title).map(l => l.id), []);
// ⭐ #82 asked for objects to live on layers and be switched off. These two are
// the ones the screen could not do at all before — "hide the units and read the
// pipes" had no control anywhere in the app.
check("positions and units are new to the screen",
      ["positions", "units"].every(
        id => SCREEN_LAYERS.some(l => l.id === id)), true);

console.log("\n🔴 a plot saved before layers existed must NOT open blank");
const old = plain();
check("no layers in the file", old.layers, undefined);
const v = visibilityOf(old);
check("the six screen layers are on",
      SCREEN_LAYERS.map(l => v[l.id]), [true, true, true, true, true, true]);
// 🔴 NOT "all true". These two defaults preserve what the app did before, and
// getting them wrong changes every PDF anyone exports from an existing plot.
check("dimensions defaults OFF, as the rulers box was unchecked",
      v.dimensions, false);
check("notes defaults ON, as the key block always printed", v.notes, true);
check("nothing is undefined",
      Object.values(v).filter(x => typeof x !== "boolean").length, 0);

console.log("\nwhat the file says wins, layer by layer");
const some = plain();
some.layers = [{ id: "pools", visible: false }, { id: "dimensions", visible: true }];
const v2 = visibilityOf(some);
check("a layer switched off in the file is off", v2.pools, false);
check("a layer switched on in the file is on", v2.dimensions, true);
// ⚠ The point of doing this per layer rather than all-or-nothing: a file that
// mentions ONE layer must not imply anything about the other seven.
check("the layers it does not mention keep their defaults",
      [v2.base, v2.units, v2.labels, v2.notes], [true, true, true, true]);

console.log("\nand a file from a LATER version still opens");
const future = plain();
// A ninth layer this build has never heard of, plus one it knows.
future.layers = [{ id: "scenery", visible: false, name: "Scenery" },
                 { id: "units", visible: false }];
const v3 = visibilityOf(future);
check("the unknown layer is ignored, not fatal",
      Object.keys(v3).includes("scenery"), false);
check("the known one is still read", v3.units, false);
check("the rest still default", v3.labels, true);

console.log("\na new plot carries all eight");
const fresh = newPlot("X");
check("seeded", (fresh.layers ?? []).map(l => l.id), LAYERS.map(l => l.id));
check("at their defaults", (fresh.layers ?? []).map(l => l.visible),
      LAYERS.map(l => l.byDefault));
check("defaultLayers agrees with the seed",
      defaultLayers(), fresh.layers);

console.log("\n🔴 the paperwork sees the whole rig, whatever is hidden");
// docs/LAYERS.md: "Layer visibility is a property of the DRAWING. The schedule,
// the hookup, the channel count and the circuit loads always report the whole
// rig." A load computed without the units somebody switched off is the failure
// that trips a breaker on a Thursday.
const av = allVisible();
check("allVisible is all eight, all true",
      Object.values(av).every(Boolean) && Object.keys(av).length, 8);
const hidden = plain();
hidden.layers = LAYERS.map(l => ({ id: l.id, visible: false }));
check("...even when the file has every layer off",
      Object.values(allVisible()).every(Boolean), true);
check("...which visibilityOf does NOT do",
      Object.values(visibilityOf(hidden)).some(Boolean), false);

console.log("\nthe store treats a toggle as an edit");
const st = new Store(plain());
check("clean to start", st.dirty, false);
st.setLayerVisible("pools", false);
check("switching a layer off marks the plot unsaved", st.dirty, true);
check("...and writes it into the file",
      (st.plot.layers ?? []).find(l => l.id === "pools")?.visible, false);
// 🔴 The whole set is written, not just the one changed. Writing one layer
// would leave a file saying "pools: off" and nothing about the other seven —
// true today, by luck, and wrong the moment a default changes.
check("...writing ALL eight, so nothing is implied",
      (st.plot.layers ?? []).length, 8);
check("...with the others at their defaults",
      visibilityOf(st.plot).dimensions, false);
check("it is undoable", st.canUndo, true);
st.undo();
check("undo brings the layer back", visibilityOf(st.plot).pools, true);

// ⚠ "Doing nothing is not a change" — the rule v0.1.21 established for
// selecting a light and retyping a value. Setting a layer to what it already is
// must not push an undo step or dirty the plot.
const st2 = new Store(plain());
st2.setLayerVisible("pools", true);          // already true by default
check("setting a layer to what it already is does nothing",
      [st2.dirty, st2.canUndo], [false, false]);

console.log("\n🔴 the markup and SCREEN_LAYERS cannot drift");
// Each chip is `id="layer-<id>"` inside the connected group, in draw order.
const group = /class="toggles"[\s\S]*?<\/span>/.exec(html)?.[0] ?? "";
check("the group is in the markup", group.length > 0, true);
const inMarkup = [...group.matchAll(/id="layer-([a-z-]+)"/g)].map(m => m[1]);
check("the chips are exactly the screen layers, in order",
      inMarkup, SCREEN_LAYERS.map(l => l.id));
for (const l of SCREEN_LAYERS) {
  const row = group.split("\n").find(line => line.includes(`id="layer-${l.id}"`)) ?? "";
  check(`${l.id}: the chip says "${l.label}"`,
        new RegExp(`>\\s*${l.label}\\s*</label>`).test(row), true);
  check(`${l.id}: its tooltip is the one in layers.ts`,
        row.includes(`title="${l.title.replace(/"/g, "&quot;")}"`), true);
}
// ⚠ The two print-only layers must NOT have a chip. A control that does nothing
// is worse than a missing one.
check("dimensions and notes have no chip",
      ["dimensions", "notes"].some(id => inMarkup.includes(id)), false);

console.log("\nthe renderer gates every layer it is given");
const render = fs.readFileSync(new URL("./render.ts", import.meta.url), "utf8");
for (const id of ["base", "pools", "positions", "focus", "units", "labels"] as LayerId[])
  check(`render.ts reads vis.${id}`, render.includes(`vis.${id}`), true);
// ⭐ The conjunctions, which are the subtle part: a label with nothing under it
// is worse than no label, so text needs its own layer AND the thing it names.
check("a position name needs labels AND positions",
      /vis\.labels && vis\.positions/.test(render), true);
check("a unit's labels need labels AND units",
      /vis\.labels && vis\.units/.test(render), true);
// ⚠ And pools and focus are deliberately NOT gated on units — where a unit's
// light lands is worth drawing with the symbols off, which is already how a
// boom's pool is drawn without a symbol.
check("pools is not gated on units",
      /vis\.pools && vis\.units/.test(render), false);
check("the old booleans are gone from the options",
      /showPools:|showFocus:|showLabels:/.test(
        render.slice(render.indexOf("export interface RenderOptions"),
                     render.indexOf("function isSelNow"))), false);

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
