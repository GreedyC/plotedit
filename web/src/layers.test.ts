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
         purposeLayers, hiddenPurposes, hiddenByPurpose, UNASSIGNED,
         isRented, rentedLayer, rentersIn, RENTED_ID,
         type LayerId } from "./layers.js";
import { newPlot, type Plot } from "./plot.js";
import type { PlotLayer } from "./layers.js";
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

console.log("\n⭐ purpose layers — derived, never stored on the instrument (#108)");
// `purpose` is ALREADY a field and already the paperwork's word for "back
// light". A backlight LAYER beside purpose:"back light" would be one fact in
// two places, and two copies of one fact drift — the bug the eight layers were
// created to fix. So the panel reads what is there.
const P = (purposes: (string | undefined)[], layers?: PlotLayer[]) => ({
  formatVersion: 1, show: "T", room: { width: 40, depth: 40 },
  positions: [], layers,
  instruments: purposes.map((purpose, n) =>
    ({ unit: n + 1, type: "S4 26", x: n, y: 20, purpose })),
} as unknown as Plot);

const names = (p: Plot) => purposeLayers(p).map(l => `${l.purpose}:${l.count}`);
check("one layer per distinct purpose, with its count",
      names(P(["back light", "front wash", "back light"])),
      ["back light:2", "front wash:1"]);
// ⚠ Bucketed as magic_sheet_rows buckets: blank AND missing are "unassigned".
// If these parted company, switching a group off on the drawing would remove a
// DIFFERENT group from the page read during tech.
check("blank and missing share the 'unassigned' bucket",
      names(P(["back light", undefined, "", "   "])),
      ["back light:1", "unassigned:3"]);
check("...and it sorts last, however it falls alphabetically",
      names(P(["zebra", undefined, "apple"])),
      ["apple:1", "zebra:1", "unassigned:1"]);
// ⭐ NOT case-folded, because exports.magic_sheet_rows is not. Folding would
// show one layer for two groups — and showing both is the only thing that ever
// surfaces the typo.
check("case is not folded", names(P(["Area 1", "area 1"])).sort(),
      ["Area 1:1", "area 1:1"]);
// ⭐ And "Area 10" sorts after "Area 9", not between 1 and 2 — these are the
// purposes a plot actually carries.
check("areas sort numerically",
      names(P(["Area 10", "Area 2", "Area 1"])),
      ["Area 1:1", "Area 2:1", "Area 10:1"]);
check("a plot with no instruments has no purpose layers", names(P([])), []);

console.log("\nvisible by default, and only the OFF state is ever written");
check("a plot that mentions none draws them all",
      purposeLayers(P(["a", "b"])).every(l => l.visible), true);
check("nothing is hidden", hiddenPurposes(P(["a", "b"])), []);
const off = P(["a", "b"], [{ id: "purpose:a", visible: false, name: "a" }]);
check("one switched off is read back off", hiddenPurposes(off), ["a"]);
check("...and the other is still on",
      purposeLayers(off).find(l => l.purpose === "b")!.visible, true);
// 🔴 THE MIGRATION AGAIN, for the new kind: a plot written before #108 mentions
// no purpose layer, and must draw every unit. Read the absence as "hidden" and
// the plot opens empty — the same one-character mistake as above.
check("an absent entry means VISIBLE, never hidden",
      hiddenPurposes(P(["a", "b", "c"])), []);

console.log("\nand the renderer asks the right question");
check("hiddenByPurpose matches on the bucket",
      hiddenByPurpose({ purpose: "a" }, new Set(["a"])), true);
check("...and the blank bucket by its name",
      hiddenByPurpose({}, new Set([UNASSIGNED])), true);
check("...and lets everything else through",
      hiddenByPurpose({ purpose: "b" }, new Set(["a"])), false);
// ⚠ The ids are namespaced because a plot may legitimately have a purpose
// called "units" — unprefixed, that would land on the built-in units layer and
// switch the whole rig off.
check("ids are namespaced", purposeLayers(P(["units"]))[0]!.id, "purpose:units");

console.log("\n🔴 the renderer draws nothing at all for a hidden unit");
// A pool with no light over it is the drawing claiming coverage from a unit the
// reader cannot see, so the gate is at the top of the loop, not per element.
check("render.ts gates the instrument loop",
      /hiddenByPurpose\(inst, hidden\)/.test(render), true);
check("...and takes the set from its options",
      /hiddenPurposes\?: ReadonlySet<string>/.test(render), true);

console.log("\n⚠ and the store keeps what it does not own");
// 🔴 setLayerVisible rebuilt plot.layers from LAYERS alone, which threw away
// every entry that was not one of the eight — the purpose layers, and also the
// ninth layer of a file written by a LATER version that visibilityOf is careful
// to carry and this then dropped on the first chip click.
const store = new Store(P(["a"], [
  { id: "purpose:a", visible: false, name: "a" },
  { id: "ninth", visible: false },
]));
store.setLayerVisible("pools", false);
const ids = (store.plot.layers ?? []).map(l => l.id);
check("a purpose layer survives a chip click", ids.includes("purpose:a"), true);
check("...and so does a layer this version has never heard of",
      ids.includes("ninth"), true);
check("...and the chip still did its job", visibilityOf(store.plot).pools, false);
check("...and the purpose is still off", hiddenPurposes(store.plot), ["a"]);

console.log("\nsetPurposeVisible, both ways");
const s2 = new Store(P(["a", "b"]));
s2.setPurposeVisible("a", false);
check("off is written", hiddenPurposes(s2.plot), ["a"]);
check("...carrying its name, because nothing in the code knows it",
      (s2.plot.layers ?? []).find(l => l.id === "purpose:a")?.name, "a");
s2.setPurposeVisible("a", true);
check("...and on again", hiddenPurposes(s2.plot), []);
check("the eight are untouched by it", visibilityOf(s2.plot).units, true);

console.log("\n⭐ the rented layer — whose is it, not what is it for (#110)");
// The presence of a NAME is the fact. No enum, because a plot hires from two
// places at once and the useful question is from whom.
const R = (rented: (string | undefined)[]) => ({
  formatVersion: 1, show: "T", room: { width: 40, depth: 40 },
  positions: [],
  instruments: rented.map((rentedFrom, n) =>
    ({ unit: n + 1, type: "S4 26", x: n, y: 20, rentedFrom })),
} as unknown as Plot);

check("a name is rented", isRented({ rentedFrom: "George" }), true);
check("absent is not", isRented({}), false);
check("empty is not", isRented({ rentedFrom: "" }), false);
// ⚠ A cell somebody tabbed through is not a hire.
check("whitespace is not", isRented({ rentedFrom: "   " }), false);

check("the layer counts the hired units",
      rentedLayer(R(["George", undefined, "Mary"]))?.count, 2);
// ⭐ BINARY, not one layer per renter. George's four and Mary's two are one set
// on the drawing — what you want to see is everything arriving in a crate.
check("...as ONE layer, however many renters",
      rentedLayer(R(["George", "Mary", "A Shop"]))?.id, RENTED_ID);
// ⚠ No chip at all when nothing is hired. A control that can only ever do
// nothing is worse than a missing one.
check("no layer when nothing is rented", rentedLayer(R([undefined, ""])), null);
check("visible by default", rentedLayer(R(["George"]))?.visible, true);
const rentOff = R(["George"]);
rentOff.layers = [{ id: RENTED_ID, visible: false, name: "rented" }];
check("...and reads back off", rentedLayer(rentOff)?.visible, false);

console.log("\nwho the units come from, which is what the order groups by");
check("counted per renter",
      rentersIn(R(["George", "Mary", "George", undefined])),
      [{ from: "George", count: 2 }, { from: "Mary", count: 1 }]);
check("sorted, numerically", rentersIn(R(["Shop 10", "Shop 2"])).map(r => r.from),
      ["Shop 2", "Shop 10"]);
check("nothing hired, nobody listed", rentersIn(R([undefined])), []);

console.log("\n🔴 the renderer hides them, and the store remembers");
check("render.ts gates on it", /opts\.hideRented && isRented\(inst\)/.test(render), true);
const s3 = new Store(R(["George", undefined]));
s3.setRentedVisible(false);
check("off is written", rentedLayer(s3.plot)?.visible, false);
check("...beside the eight, not instead of them",
      visibilityOf(s3.plot).units, true);
s3.setRentedVisible(true);
check("...and on again", rentedLayer(s3.plot)?.visible, true);
// 🔴 The same keeps-what-it-does-not-own rule as the purpose layers.
const s4 = new Store(R(["George"]));
s4.setRentedVisible(false);
s4.setLayerVisible("pools", false);
check("a chip click does not drop it", rentedLayer(s4.plot)?.visible, false);

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");
