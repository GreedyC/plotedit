import assert from "node:assert/strict";
import { attachPointer } from "./interact.js";
import { Store } from "./store.js";
import type { Plot } from "./plot.js";

class Surface extends EventTarget {
  style = { cursor: "crosshair" };
  captures = new Set<number>();
  setPointerCapture(id: number) { this.captures.add(id); }
  releasePointerCapture(id: number) { this.captures.delete(id); }
  getBoundingClientRect() { return { left: 0, top: 0 }; }
}
const surface = new Surface();
const store = new Store({ formatVersion: 1, show: "T", room: { width: 40, depth: 40 },
  positions: [], instruments: [{ unit: 1, type: "S4 26", x: 5, y: 20 }] } as Plot);
const pans: number[][] = [];
let changes = 0, settled = 0;
const ctx = {
  view: () => ({ scale: 10, panX: 0, panY: 0, width: 400, height: 400 }),
  onChange: () => { changes++; }, onSettled: () => { settled++; },
  onPan: (dx: number, dy: number) => { pans.push([dx, dy]); },
};
attachPointer(surface as unknown as SVGSVGElement, store, ctx);
function pointer(type: string, x: number, y: number, options: Record<string, unknown> = {}) {
  const event = new Event(type, { cancelable: true });
  const { target, ...rest } = options;
  Object.assign(event, { clientX: x, clientY: y, pointerId: 1, button: 0, shiftKey: false,
    altKey: false, ...rest });
  if (options.target) Object.defineProperty(event, "target", { value: options.target });
  surface.dispatchEvent(event);
  return event;
}
(surface as unknown as { closest: () => null }).closest = () => null;
store.select(0);
pointer("pointerdown", 100, 100);
assert.equal(surface.style.cursor, "grabbing");
assert.equal(surface.captures.has(1), true);
pointer("pointermove", 125, 90);
pointer("pointermove", 135, 105);
assert.deepEqual(pans, [[25, -10], [35, 5]]);
assert.equal(store.dirty, false);
assert.deepEqual(store.plot.instruments[0], { unit: 1, type: "S4 26", x: 5, y: 20 });
assert.equal(changes, 0);
pointer("pointerup", 135, 105);
assert.equal(surface.style.cursor, "crosshair");
assert.equal(surface.captures.size, 0);
assert.equal(settled, 0);
pointer("pointermove", 150, 110);
assert.equal(pans.length, 2);

pointer("pointerdown", 100, 100, { button: 2 });
pointer("pointermove", 120, 100);
assert.equal(pans.length, 2);
pointer("pointerdown", 100, 100);
pointer("pointermove", 120, 100, { pointerId: 2 });
assert.equal(pans.length, 2);
pointer("pointercancel", 100, 100);
assert.equal(surface.style.cursor, "crosshair");
assert.equal(surface.captures.size, 0);

const unit = { closest: () => unit, getAttribute: (name: string) => name === "data-index" ? "0" : "body" };
pointer("pointerdown", 50, 200, { target: unit });
pointer("pointermove", 70, 190, { altKey: true });
pointer("pointerup", 70, 190);
assert.equal(store.plot.instruments[0]!.x, 7);
assert.equal(store.plot.instruments[0]!.y, 21);
assert.equal(settled, 1);
assert.equal(pans.length, 2);
store.undo();
assert.equal(store.plot.instruments[0]!.x, 5);

const position = { getAttribute: () => "0" };
const pipe = { closest: (query: string) => query === "[data-position]" ? position : null };
pointer("pointerdown", 100, 100, { target: pipe });
pointer("pointermove", 120, 100);
assert.equal(pans.length, 2);

attachPointer(surface as unknown as SVGSVGElement, store, ctx);
pointer("pointerdown", 100, 100);
pointer("pointermove", 110, 100);
pointer("pointerup", 110, 100);
assert.deepEqual(pans, [[25, -10], [35, 5], [10, 0]]);
console.log("pointer panning, cancellation, reattachment and instrument dragging passed");

pointer("pointerdown", 100, 100);
attachPointer(surface as unknown as SVGSVGElement, store, ctx);
assert.equal(surface.style.cursor, "crosshair");
assert.equal(surface.captures.size, 0);
pointer("pointermove", 140, 100);
assert.equal(pans.length, 3);
pointer("pointerdown", 100, 100);
pointer("lostpointercapture", 100, 100);
assert.equal(surface.style.cursor, "crosshair");

pointer("pointerdown", 50, 200, { target: unit });
pointer("pointermove", 70, 190, { altKey: true });
attachPointer(surface as unknown as SVGSVGElement, store, ctx);
assert.equal(surface.captures.size, 0);
store.undo();
assert.equal(store.plot.instruments[0]!.x, 5);
pointer("pointermove", 100, 100);
assert.equal(store.plot.instruments[0]!.x, 5);

store.select(0);
pointer("pointerdown", 100, 100);
pointer("pointerup", 100, 100);
assert.equal(store.selected, null);
const focus = { closest: () => focus, getAttribute: (name: string) => name === "data-index" ? "0" : "focus" };
pointer("pointerdown", 50, 200, { target: focus });
pointer("pointermove", 60, 210);
pointer("pointerup", 60, 210);
assert.equal(store.plot.instruments[0]!.x, 5);
assert.equal(store.plot.instruments[0]!.y, 20);
assert.equal(store.plot.instruments[0]!.focusX, 6);
assert.equal(store.plot.instruments[0]!.focusY, 19);
store.undo();
assert.equal(store.plot.instruments[0]!.focusX, undefined);
