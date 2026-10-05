/*
 * plotedit — a light plot editor for small rigs.
 * Copyright (C) 2026 Jerry Jonas
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <https://www.gnu.org/licenses/>.
 */
/** Load a plot, draw it, let it be edited. */
import { fitView, fohExtent, setUnitSystem, fmtFt, toPlot, type View, placeBase,
         toScreen } from "./geometry.js";
import { isPlot, symbolKey, plotFileName, newPlot, type Plot, type Position,
         lengthOf, angleOf, runOf } from "./plot.js";
import { startSeq, seqClick, clickLine, seqReport, runIndices,
         type Seq } from "./sequence.js";
import { openMenu, type MenuGroup, type MenuItem } from "./menu.js";
import { visibilityOf, SCREEN_LAYERS } from "./layers.js";
import { confirmRevert } from "./confirm.js";
import { render, POS_CHAR_W, POS_TEXT, type Computed, type RenderOptions } from "./render.js";
import { compute, fixtures, exportFile, dxfLayers, dxfPaths, symbols, booms,
         positionLabels, savePlot, listPlots, pickPlotsFolder, loadPlot, pdfPages, pdfPaths,
         serverVersion,
         type FixtureRow, type ExportKind, type DxfPaths, type SymbolPrim,
         type BoomElevation, type PositionLabel,
         dmxTable, gelList, paperSizes, samples, readSample, pdfRaster,
         type DmxTable, type PaperSize } from "./api.js";
import { parseFeet } from "./feet.js";
import { Store } from "./store.js";
import { attachPointer, attachKeyboard } from "./interact.js";
import { renderInspector } from "./inspector.js";
import { renderPositions } from "./positions.js";
import { renderDetails } from "./details.js";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const svg = $<HTMLElement>("plot") as unknown as SVGSVGElement;

let store: Store;
let computed: Computed[] = [];
let fixtureTable: Record<string, FixtureRow> = {};
/** The DMX personalities. ⚠ Undefined until it arrives, and the two dropdowns
 *  offer nothing rather than guessing in the meantime. */
let dmxTable_: DmxTable | undefined;
let gelList_: { gel: string; name: string }[] | undefined;
let paperSizes_: { imperial: PaperSize[]; metric: PaperSize[]; default: string } | undefined;
// ⭐ A ground plan with no vectors in it — a photograph, a scan, a planner's
// layout — placed as a BACKDROP to draw over. 🔴 NEVER A MEASUREMENT: the
// room's dimensions are still typed in by whoever measured them, and `wide`
// is only how big the picture is DRAWN.
let baseImage: { href: string; aspect: number; x: number; y: number;
                 wide: number; rotate: number; opacity: number } | undefined;
// Two clicks and a real distance set the scale. Held here while the mode runs.
let calibrating: { a?: { x: number; y: number } } | undefined;
// ⭐ Drawing a pipe by pointing at its ends. Same shape as `calibrating` and for
// the same reason — a mode the PLAN is in, not a dialog, because the thing you
// are aiming at is the room.
let drawingPipe: { pos: Position; a?: { x: number; y: number } } | undefined;
let pipeGhost: SVGLineElement | undefined;
// ⭐ The SAME placement for a vector base. dxf_bridge has taken an offset and a
// rotation since the beginning and no endpoint ever exposed them, so an import
// that landed in the wrong place could only be lived with — #63.
let baseXf = { x: 0, y: 0, rotate: 0 };
let basePlan: DxfPaths | null = null;

/**
 * Forget the imported ground plan.
 *
 * 🔴 THE IMPORT IS NOT PART OF THE PLOT, and that is what made it follow people
 * around. `basePlan`, `baseImage` and `baseXf` live here in the module, not in
 * the file — so opening a different plot left the previous venue's drawing
 * underneath it. A tester imported a DXF, opened the demo, and his plan was
 * still there with no obvious way out. (Reported 2026.10.05.)
 *
 * ⚠ The object URL has to be revoked, or a session of trying plans holds every
 * one of them in memory until the tab closes. That was already right in the off
 * button; this exists so the open path cannot forget it.
 */
function clearBase(): void {
  if (baseImage) URL.revokeObjectURL(baseImage.href);
  baseImage = undefined;
  basePlan = null;
  baseXf = { x: 0, y: 0, rotate: 0 };
}
let symbolCache: Record<string, SymbolPrim[]> = {};

/** The whole drawing's size in FEET — room, house, boom elevations and margin. */
function drawingFeet(): { w: number; h: number; house: number } {
  const { width, depth } = store.plot.room;
  // ⭐ The canvas has to be tall enough for the HOUSE as well as the stage.
  // Front-of-house positions sit at negative y, and a view fitted to the room
  // alone simply does not show them — no warning, no clipping guard, just a
  // catwalk that is not there.
  const house = fohExtent(store.plot.positions);
  // ⭐ And WIDE enough for the boom elevations, which sit off the stage-left
  // edge at negative x. The server says how much room they need — the same
  // figure plot_to_pdf uses to set its origin.
  return { w: width + boomSpace + VIEW_MARGIN * 2,
           h: depth + house + VIEW_MARGIN * 2, house };
}

function view(): View {
  const pxPerFoot = Number($<HTMLInputElement>("zoom").value);
  const { width, depth } = store.plot.room;
  const { w, h, house } = drawingFeet();
  return fitView(width, depth, w * pxPerFoot, h * pxPerFoot, VIEW_MARGIN, house, boomSpace);
}

/** The height to cut the pools at. Aiming and cutting are different choices:
 *  a unit aimed at a face still throws a much larger pool on the deck. */
/** How much width the §6.12 boom elevations need, in feet. Filled by the
 *  server; 0 until it answers, which simply means no elevations are drawn yet. */
/** Clear air drawn around the room, in feet. Also what a position name is
 *  allowed to use beyond the walls. */
const VIEW_MARGIN = 4;
let boomSpace = 0;
let boomLayout: BoomElevation[] = [];
let labelLayout: PositionLabel[] = [];

function poolPlane(): number | undefined {
  const v = ($<HTMLSelectElement>("poolplane")?.value ?? "");
  return v === "" ? undefined : Number(v);
}

function opts(): RenderOptions {
  return {
    // 🔴 FROM THE PLOT, NOT FROM THE CHECKBOXES. The chips are an input to
    // the plot's layer state, not the place it lives — so undo, Revert and
    // opening a file all change what is drawn without anything having to
    // remember to tick a box. The chips are synced FROM here, in syncLayers().
    layers: visibilityOf(store.plot),
    selected: store.selected,
    selectedPosition: store.selectedPosition,
    // ⚠ Both kinds of base are passed unconditionally now and the renderer
    // decides. The same layer governs lines and a picture alike: a designer who
    // turns the plan off means the imported one, whichever it is.
    basePaths: placedBasePaths(),
    baseImage: baseImage
      ? { href: baseImage.href, x: baseImage.x, y: baseImage.y,
          wide: baseImage.wide, tall: baseImage.wide * baseImage.aspect,
          rotate: baseImage.rotate, opacity: baseImage.opacity }
      : undefined,
    symbols: symbolCache,
    booms: boomLayout,
    labels: labelLayout,
  };
}

/** The scale menu offers the scales the PLOT can be drawn at.
 *
 * ⚠ Imperial fractions or metric ratios, never both. 1/4" = 1'-0" IS 1:48, so
 * a metric plot could be drawn at 1/4" and be arithmetically fine — and no
 * reader would have that ratio on their scale rule. The restriction is about
 * the person at the other end, not about the numbers.
 *
 * ⚠ "Fit" is kept whatever the system, and the CURRENT choice survives when it
 * is still on offer — rebuilding the menu on every draw would otherwise reset
 * a chosen scale back to Fit on any edit.
 */
function fillScaleMenu(): void {
  const sel = $<HTMLSelectElement>("scale");
  const metric = (store.plot.units ?? "imperial") === "metric";
  const want = metric
    ? ["1:10", "1:20", "1:25", "1:50", "1:100"]
    : ["1", "3/4", "1/2", "3/8", "1/4", "1/8"];
  const have = Array.from(sel.options).slice(1).map(o => o.value);
  if (have.join() === want.join()) return;           // nothing to do
  const chosen = sel.value;
  while (sel.options.length > 1) sel.remove(1);
  for (const v of want) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = metric ? v : `${v}"`;
    sel.appendChild(o);
  }
  sel.value = want.includes(chosen) ? chosen : "fit";
}

/** The sheet menu, built the same way and for the same reason as the scale one.
 *
 * ⚠ Imperial sheets or metric sheets, never both — ARCH D on a metric plot is
 * the same mistake as 1/4" on one. The list comes from the SERVER; a second
 * copy here is how the lamp dropdown fell a release behind its own table.
 *
 * Until /pages answers, the menu holds one entry saying what the export will do
 * anyway, rather than sitting empty and looking broken.
 */
function fillPageMenu(): void {
  const sel = $<HTMLSelectElement>("page");
  const metric = (store.plot.units ?? "imperial") === "metric";
  const rows = metric ? paperSizes_?.metric : paperSizes_?.imperial;
  if (!rows) {
    if (!sel.options.length) {
      const o = document.createElement("option");
      o.value = ""; o.textContent = "ARCH D";
      sel.appendChild(o);
    }
    return;
  }
  const want = rows.map(r => r.name);
  const have = Array.from(sel.options).map(o => o.value);
  if (have.join() === want.join()) return;
  const chosen = sel.value;
  sel.replaceChildren();
  for (const r of rows) {
    const o = document.createElement("option");
    o.value = r.name;
    o.textContent = r.label;
    o.title = `${(r.w_in * 25.4).toFixed(0)} x ${(r.h_in * 25.4).toFixed(0)} mm`;
    sel.appendChild(o);
  }
  // ⭐ Keep the sheet the designer picked if it still exists on this side of the
  // units switch; otherwise fall back to the server's default, not to the first
  // in the list — the first is the SMALLEST, and silently issuing a D-sized plot
  // on Letter is the kind of thing nobody notices until it is printed.
  sel.value = want.includes(chosen) ? chosen
            : want.includes(paperSizes_?.default ?? "") ? paperSizes_!.default
            : want[want.length - 1]!;
}

function draw() {
  // ⚠ Before ANYTHING is formatted. The system is ambient (see geometry.ts) and
  // this is the single place it is refreshed — a draw that ran with a stale one
  // would label a metric plot in feet and look like a conversion bug rather
  // than a missing assignment.
  setUnitSystem(store.plot.units);
  fillScaleMenu(); fillPageMenu(); syncSheetInfo(); render(svg, store.plot, view(), computed, opts()); }

/** The dimmer, or the address where there is no dimmer, and which of the two it
 *  is. ⚠ ONE COLUMN CANNOT SAY WHICH ON ITS OWN — "12" is a plausible dimmer and
 *  a plausible address, and a patch column that leaves that open is how a unit
 *  gets plugged into the wrong thing. The number is what is read at a glance;
 *  the hover says what it is. */
function patchCell(inst: { address?: unknown; dimmer?: unknown }): [string, string] {
  const filled = (v: unknown) => v !== undefined && v !== null && String(v).trim() !== "";
  if (filled(inst.address)) return [String(inst.address).trim(), "address"];
  if (filled(inst.dimmer)) return [String(inst.dimmer).trim(), "dimmer"];
  return ["—", "no dimmer and no address — this unit is not patched to anything"];
}


function fillTable() {
  const tb = $<HTMLTableElement>("schedule").querySelector("tbody")!;
  tb.replaceChildren();
  store.plot.instruments.forEach((inst, i) => {
    const c = computed[i];
    const tr = document.createElement("tr");
    tr.dataset.index = String(i);
    if (i === store.selected) tr.classList.add("sel");
    // ⭐ The server's answer wins. patchCell is the fallback for the moment
    // before the first compute returns, and it knows nothing about footprints —
    // it can show a start address but never a range.
    const [fallback, fallbackWhy] = patchCell(inst);
    const patchText = c?.patch ?? fallback;
    const patchWhat = c?.patch_note ?? fallbackWhy;
    const cells: [string, boolean, string?][] = [
      [inst.position ?? "", false], [String(inst.unit), false],
      [inst.channel !== undefined ? String(inst.channel) : "", false],
      [inst.type, false], [inst.color ?? "—", false],
      // ⚠ UNKNOWN, never a blank. An empty cell in a load column reads as
      // "nothing on that circuit", which is how a dimmer gets loaded past its
      // rating on paper.
      [c ? (c.watts != null ? `${c.watts}` : "UNKNOWN") : "—", true],
      // ⭐ Jerry, 2026.09.26: the throw, the pool and the footcandles came off
      // this table and the patch went on. Those three are design figures, and
      // the inspector already gives them for the unit in hand; this list is
      // read while working through a rig, where what is wanted is what each
      // unit is plugged into.
      //
      // ⚠ An address and a dimmer are ALTERNATIVES, not a pair — the same rule
      // the Eos exporter follows in _patch_target. The address wins when a unit
      // carries both, because that is the number the console uses.
      [patchText, true, patchWhat],
    ];
    for (const [text, num, hover] of cells) {
      const td = document.createElement("td");
      if (num) td.className = "num";
      if (hover) td.title = hover;
      td.textContent = text;
      tr.appendChild(td);
    }
    if (c && !c.computed) tr.classList.add("warn");
    tr.title = c?.footcandles_note ?? c?.note ?? "";
    tr.addEventListener("click", () => store.select(i));
    tb.appendChild(tr);
  });
}

function drawInspector() {
  // ⚠ Two callbacks, because two kinds of field. A designer's name only prints;
  // a room width moves every position and every check that depends on one.
  // Wiring both to draw() would leave the throws and the headroom warnings
  // describing a room that is no longer there.
  renderDetails($("details"), store, {
    onChange: () => { paintChrome(); draw(); },
    onGeometry: () => { paintChrome(); draw(); recompute(); },
  });
  renderPositions($("positions"), store, {
    onChange: () => { draw(); recompute(); },
    onStatus: (msg, bad) => status(msg, bad),
    onDrawPipe: (pos) => startPipeDraw(pos),
    onNumberSeq: (pos, start) => startNumbering(pos, start),
  });
  renderInspector($("inspector"), store, computed, {
    fixtures: Object.keys(fixtureTable).sort(),
    dmx: dmxTable_,
    gels: gelList_,
    // ⭐ The FAMILY decides which specific models to offer, and it is the
    // server's answer, not a list kept here.
    familyOf: (t: string) => fixtureTable[t]?.family,
    // ⭐ The server's own answer, not a list kept here — which is the whole
    // argument of docs/LAMP-AND-MODE.md, applied to the one field that
    // could already be answered without new data.
    modesFor: (t: string) => fixtureTable[t]?.modes ?? [],
    // ⚠ STILL HARDCODED. The lamps live in LAMP_MF in Python and this is a
    // second copy of them kept by hand, so it drifts — it drifted for a whole
    // release. Keep the two in step until docs/LAMP-AND-MODE.md is acted on
    // and the server answers this the way it already answers `fixtures`.
    //
    // ⭐ HPL 550/77 is the DIMMER DOUBLING lamp (Jerry, 2026.09.29) — 550W
    // at 77 volts, and the low voltage is the point. Nothing on the plot
    // yet says which circuits are doubled, so choosing it here is a
    // statement about the lamp only. HPL 375 next to it is an ordinary
    // 115V lamp you fit to halve the load; the two are not the same trick.
    //
    // ⭐ THE LAST THREE ARE NOT LAMPS IN THE USUAL SENSE (Jerry, 2026.09.29).
    // Pull the HPL out of a Source Four, drop a 4WRD in, and the barrel is an
    // LED — same tube, same angles, 150W instead of 575. They belong on this
    // list because that is how you ORDER them and how the rig is built, and
    // because the photometrics key off the lamp. The three are separate part
    // numbers, not modes of one product, which is why there are three.
    lamps: ["HPL 750", "HPL 575", "HPL 575X", "HPL 375", "HPL 550/77",
            "Source 4WRD II", "Source 4WRD II Gallery",
            "Source 4WRD II Daylight Gallery"],
    modes: ["Boost Full", "Regulated Full", "Regulated 3200K", "Regulated 5600K"],
    onStatus: (msg, bad) => status(msg, bad),
    onPhotometricChange: () => { paint(); recompute(); },
    onPaperworkChange: () => paint(),
  });
}

/** Redraw everything from current state. Cheap — no network. */
function paint() {
  syncLayers();
  draw();
  fillTable();
  drawInspector();
  paintChrome();
  // ⚠ Clicking a light has to SHOW the light. Leaving the Instrument panel shut
  // while its fields quietly change behind the header is worse than the space
  // it costs — the click would look like it did nothing.
  if (store.selected !== null) {
    const inst = document.getElementById("panel-instrument") as HTMLDetailsElement | null;
    if (inst && !inst.open) inst.open = true;
  }
  $("dirty").textContent = store.dirty ? "Unsaved changes" : "";
  ($("undo") as HTMLButtonElement).disabled = !store.canUndo;
  ($("redo") as HTMLButtonElement).disabled = !store.canRedo;
  // ⭐ Jerry, 2026.09.30: "make the UI save button inactive if there is nothing
  // to save." It sits with undo and redo because it is the same rule — a control
  // that cannot do anything should not look like it can.
  //
  // ⚠ SAVE ONLY, never Save As. Saving a copy under a new name is a real thing
  // to want with nothing changed, and it is also the only way to write a plot
  // that has never been saved — `save()` falls through to `saveAs()` when there
  // is no file name yet, and a brand new plot is not dirty.
  //
  // The title changes with it. A greyed button with no explanation is a puzzle.
  const saveBtn = $("save") as HTMLButtonElement;
  saveBtn.disabled = !store.dirty;
  saveBtn.title = store.dirty ? "Save (⌘S)" : "No changes to save";
  // Revert follows the same rule, and for the same reason: with nothing changed
  // there is nothing to go back from.
  const revertBtn = $("revert") as HTMLButtonElement;
  revertBtn.disabled = !store.dirty || !onDisk;
  revertBtn.title = store.dirty
    ? "Reload the plot from disk, dropping every change since"
    : "Nothing has changed since this was opened";
  // ⭐ Each section header says what is IN it. The three panels were three grey
  // blocks that had to be read to be told apart; a count in the header answers
  // "which one is this" and "is there anything here" in one glance.
  const sel = store.selected;
  const inst = sel === null ? undefined : store.plot.instruments[sel];
  $("inst-count").textContent = inst
    ? `Unit ${inst.unit}${inst.channel === undefined ? "" : ` · ch ${inst.channel}`}`
    : "none selected";
  $("pos-count").textContent = String(store.plot.positions.length);
  $("sched-count").textContent = String(store.plot.instruments.length);
}

/** Remember which panels are open, per browser.
 *
 * ⭐ Jerry, 2026.09.24: "can the cards showing positions, schedule, show etc be
 * accordions so they don't take up real estate when we don't want them."
 * Collapsing one is only useful if it STAYS collapsed — reopening everything on
 * every reload would mean doing the tidying again each time.
 *
 * ⚠ localStorage throws in a private window and can come back empty, so every
 * read and write is guarded and the panels simply default to open. A layout
 * preference is not worth an exception that stops the editor loading.
 */
const PANELS = ["details", "instrument", "positions", "schedule"] as const;

function wirePanels(): void {
  for (const name of PANELS) {
    const el = document.getElementById(`panel-${name}`) as HTMLDetailsElement | null;
    if (!el) continue;
    try {
      const saved = localStorage.getItem(`plotedit.panel.${name}`);
      if (saved !== null) el.open = saved === "1";
    } catch { /* no storage — leave it open */ }
    el.addEventListener("toggle", () => {
      try { localStorage.setItem(`plotedit.panel.${name}`, el.open ? "1" : "0"); }
      catch { /* nothing to do; the panel still works this session */ }
    });
  }
}

/** The splitter between the drawing and the side panel.
 *
 * ⭐ Tim, 2026.09.25: make the side panel wider "and not need to use the
 * horizontal scrollbar for some content." Dragged width is remembered per
 * browser, with the same guarded storage as the panels; double-click resets.
 */
const ASIDE_DEFAULT = 380, ASIDE_MIN = 280, CANVAS_MIN = 240;
/** The splitter's own column, and it has to be paid for. */
const SPLITTER_W = 6;

function wireSplitter(): void {
  const main = document.querySelector("main") as HTMLElement;
  const bar = $("splitter");
  // ⚠ THE SPLITTER IS A COLUMN TOO. The grid is `1fr | 6px | aside`, so the
  // drawing gets (width − splitter − aside). Clamping against the width alone
  // left the canvas 234px against an advertised 240 — six pixels, but the
  // number the code promises is the number it should keep.
  //
  // ⚠ And measured off MAIN rather than the window. They are the same today;
  // the moment anything sits beside main they are not, and the one that
  // matters is the box the grid is actually laid out in.
  const clamp = (w: number) => {
    const room = main.clientWidth || window.innerWidth;
    return Math.round(Math.max(ASIDE_MIN,
                               Math.min(w, room - CANVAS_MIN - SPLITTER_W)));
  };
  const set = (w: number) => main.style.setProperty("--aside-w", `${clamp(w)}px`);
  const current = () =>
    parseFloat(getComputedStyle(main).getPropertyValue("--aside-w")) || ASIDE_DEFAULT;
  const save = (w: number | null) => {
    try {
      if (w === null) localStorage.removeItem("plotedit.asideWidth");
      else localStorage.setItem("plotedit.asideWidth", String(clamp(w)));
    } catch { /* the width still applies this session */ }
  };
  try {
    const saved = Number(localStorage.getItem("plotedit.asideWidth"));
    if (saved > 0) set(saved);
  } catch { /* no storage — default width */ }

  let dragging = false;
  const widthAt = (clientX: number) => main.getBoundingClientRect().right - clientX;
  bar.addEventListener("pointerdown", (e) => {
    dragging = true;
    bar.setPointerCapture(e.pointerId);
    bar.classList.add("dragging");
    document.body.classList.add("resizing");
    e.preventDefault();
  });
  bar.addEventListener("pointermove", (e) => { if (dragging) set(widthAt(e.clientX)); });
  const end = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    bar.classList.remove("dragging");
    document.body.classList.remove("resizing");
    save(widthAt(e.clientX));
  };
  bar.addEventListener("pointerup", end);
  bar.addEventListener("pointercancel", end);
  bar.addEventListener("dblclick", () => { set(ASIDE_DEFAULT); save(null); });

  // ⚠ Re-clamp when the WINDOW changes, not only when the splitter is dragged.
  // A width saved on a wide screen is restored whole on a narrow one, and
  // nothing was re-checking it — so the drawing could be squeezed under its
  // minimum, or behind `overflow:hidden` entirely, without a pointer ever
  // touching the splitter. The saved value is left alone: the reader still
  // wants that width back when the window is wide again.
  window.addEventListener("resize", () => set(current()));

  // ⭐ Keyboard, because this declares role="separator". Announcing a control
  // and then only accepting a pointer is worse than not announcing it: a
  // screen reader offers the reader something they cannot use.
  bar.tabIndex = 0;
  bar.setAttribute("aria-label", "Side panel width");
  const announce = () => {
    bar.setAttribute("aria-valuenow", String(Math.round(current())));
    bar.setAttribute("aria-valuemin", String(ASIDE_MIN));
    bar.setAttribute("aria-valuemax",
                     String(Math.round((main.clientWidth || window.innerWidth)
                                       - CANVAS_MIN - SPLITTER_W)));
  };
  announce();
  bar.addEventListener("keydown", (e) => {
    const STEP = e.shiftKey ? 48 : 12;
    let w: number | null = null;
    if (e.key === "ArrowLeft") w = current() + STEP;       // left widens the panel
    else if (e.key === "ArrowRight") w = current() - STEP;
    else if (e.key === "Home") w = ASIDE_MIN;
    else if (e.key === "End") w = Infinity;                // clamped to the max
    else if (e.key === "Enter" || e.key === " ") { set(ASIDE_DEFAULT); save(null); announce(); e.preventDefault(); return; }
    if (w === null) return;
    set(w); save(current()); announce();
    e.preventDefault();
  });
}

/** Zoom presets beside the slider: whole plot, fit height, fit width, 100%.
 *  "100%" is the slider's default of 14 px per foot, the editor's home zoom. */
const ZOOM_DEFAULT = 14;

function wireZoomButtons(): void {
  const slider = $<HTMLInputElement>("zoom");
  const canvas = $("canvas");
  const setZoom = (px: number) => {
    const lo = Number(slider.min), hi = Number(slider.max), step = Number(slider.step);
    slider.value = String(Math.max(lo, Math.min(hi, Math.floor(px / step) * step)));
    draw();
  };
  // ⚠ Measured ONCE and reused. It adds a probe element to the document to
  // find the scrollbar's width, and doing that inside every fit meant three
  // layout flushes to answer a question whose answer does not change.
  let barW: number | null = null;
  const bar = () => {
    if (barW !== null) return barW;
    const probe = document.createElement("div");
    probe.style.cssText = "position:absolute;visibility:hidden;overflow:scroll;width:100px;height:100px";
    document.body.append(probe);
    barW = probe.offsetWidth - probe.clientWidth;
    probe.remove();
    return barW;
  };

  // The room a fitted drawing would have, less the canvas's padding.
  //
  // 🔴 clientWidth ALREADY EXCLUDES a scrollbar that is showing right now, so
  // it is not the scrollbar-free room this needs — it is the room as things
  // currently stand. Click fit-width while a vertical scrollbar happens to be
  // up and its width came off twice: once here, and again in the adjustment
  // below. The drawing came out a little small and nothing said why.
  //
  // So: add back whichever bars are up, to get the room as if none were, and
  // let the caller take one off again only for the axis that really overflows.
  const room = () => {
    const cs = getComputedStyle(canvas);
    const vUp = canvas.scrollHeight > canvas.clientHeight + 1;
    const hUp = canvas.scrollWidth > canvas.clientWidth + 1;
    return {
      w: canvas.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
         + (vUp ? bar() : 0),
      h: canvas.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)
         + (hUp ? bar() : 0),
    };
  };
  $("zoom-page").addEventListener("click", () => {
    const r = room(), d = drawingFeet();
    setZoom(Math.min(r.w / d.w, r.h / d.h));
  });
  // ⚠ Fitting ONE side lets the other overflow, and the scrollbar that brings
  // takes its width out of the side just fitted — fit-to-width then needs a
  // horizontal scrollbar too. Leave room for it when the other side overflows.
  $("zoom-height").addEventListener("click", () => {
    const r = room(), d = drawingFeet();
    let px = r.h / d.h;
    if (d.w * px > r.w) px = (r.h - bar()) / d.h;
    setZoom(px);
  });
  $("zoom-width").addEventListener("click", () => {
    const r = room(), d = drawingFeet();
    let px = r.w / d.w;
    if (d.h * px > r.h) px = (r.w - bar()) / d.w;
    setZoom(px);
  });
  $("zoom-100").addEventListener("click", () => setZoom(ZOOM_DEFAULT));
}

/**
 * Put the chips where the PLOT says they are.
 *
 * 🔴 THE CHIPS ARE A VIEW OF THE FILE, not the state itself. Layer
 * visibility lives in the plot (Jerry: "the plot file needs to have the
 * layers"), so undo, Revert, Open and New all change it — and a checkbox that
 * only changed when clicked would show the old answer after any of them. This
 * runs on every paint, which is every one of those paths.
 *
 * ⚠ `dimensions` and `notes` have no chip. They are carried in the file and
 * read by the export; there is nothing on screen for a chip to change, and a
 * control that does nothing is worse than a missing one.
 */
function syncLayers(): void {
  const vis = visibilityOf(store.plot);
  for (const l of SCREEN_LAYERS) {
    const box = document.getElementById(`layer-${l.id}`) as HTMLInputElement | null;
    if (box && box.checked !== vis[l.id]) box.checked = vis[l.id];
  }
}

/** The header's own copy of the show and venue, so editing them in the panel
 *  is visibly the same fact as the one at the top of the window. */
function paintChrome(): void {
  $("show").textContent = store.plot.show || "Untitled";
  $("venue").textContent =
    [store.plot.venue, store.plot.revision].filter(Boolean).join(" · ");
  $("det-count").textContent = store.plot.venue || "no venue";
}

/** Fetch RP-2 outlines for any fixture type not already held. */
async function ensureSymbols() {
  const want = [...new Set(store.plot.instruments.map(symbolKey))]
    .filter(t => t && !(t in symbolCache));
  if (!want.length) return;
  try {
    Object.assign(symbolCache, await symbols(want));
  } catch (e) {
    // Drawing the wrong shape is worse than drawing a plain ring, which is
    // what render() falls back to when a type is missing from the cache.
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Where the §6.12 boom elevations go. Asked of the server, never worked out
 *  here: the compression is a drawing decision, and a second copy of it in
 *  TypeScript is how the screen and the paper drifted three times in a week. */
async function ensureBooms() {
  try {
    const r = await booms(store.plot);
    boomLayout = r.booms;
    boomSpace = r.space;
  } catch (e) {
    // ⚠ Say so. A boom whose elevation failed to load is a boom whose units are
    // not on the drawing at all — silence would read as "there are none".
    boomLayout = [];
    boomSpace = 0;
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Where the position names go, fitted around the units and each other. Asked
 *  of the server so the screen and the paper choose the same slots. */
async function ensureLabels() {
  try {
    // ⚠ The canvas edge, in plot feet. Without it the fitter will happily put
    // a long name in clear air past the stage-right wall — clear of every
    // symbol and off the side of the view, which is a position with no name.
    // The margin is a CONSTANT chosen before fitting, so there is no circle
    // between "where do the labels go" and "how wide is the canvas".
    const { width, depth } = store.plot.room;
    labelLayout = await positionLabels(store.plot, POS_CHAR_W, POS_TEXT,
      [-boomSpace, -VIEW_MARGIN, width + VIEW_MARGIN, depth + VIEW_MARGIN]);
  } catch (e) {
    // ⚠ Fall back to the old stage-left-end placement rather than dropping the
    // names. A collision is untidy; an unnamed pipe is unusable.
    labelLayout = [];
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Ask the Python what the light does. Debounced — a drag is one request. */
let pending: ReturnType<typeof setTimeout>;
function recompute(delay = 120) {
  clearTimeout(pending);
  pending = setTimeout(async () => {
    try {
      computed = await compute(store.plot, poolPlane());
      await ensureSymbols();
      await ensureBooms();
      await ensureLabels();
      paint();
    } catch (e) {
      showError(e);
    }
  }, delay);
}

/** The file on disk this plot belongs to, or null for one never saved.
 *
 * ⭐ Jerry, 2026.09.24: "the save is not automatically overwriting the file —
 * it tries a new name Without Consent.plot (1).json." That bracket is the
 * browser's DOWNLOAD behaviour. Save was built on the File System Access API,
 * which can overwrite in place — but only Chrome and Edge have it, so anywhere
 * else every press dropped another copy in Downloads and the real plot was
 * whichever had the longest number in brackets.
 *
 * ⚠ ONE code path now, through the server, which has a filesystem and needs no
 * permission to use it. Two paths — a browser API here, a server call there —
 * would mean Save behaved differently on different machines, which is exactly
 * the class of divergence that has cost a day already in this repo.
 */
let savedAs: string | null = null;
/** The plot as it is on disk — what Revert goes back to. Set when a plot is
 *  adopted and again on every save. */
let onDisk: Plot | null = null;

function plotJson(): string {
  return JSON.stringify(store.plot, null, 2);
}

async function saveTo(name: string): Promise<void> {
  const { path } = await savePlot(name, store.plot);
  savedAs = name;
  // ⚠ Saving MOVES the point Revert goes back to. "As you opened it" and "as it
  // is on disk" are the same thing until you save, and after that only the
  // second one is coherent — reverting to a pre-save state would leave the
  // editor disagreeing with a file it had just written, and still calling
  // itself clean. Revert means "reload from disk".
  onDisk = structuredClone(store.plot);
  store.markSaved();
  status(`Saved ${path}`);
  void refreshOpenList();
}

async function saveAs(): Promise<void> {
  const suggested = savedAs ?? plotFileName(store.plot.show);
  const name = window.prompt(
    "Save this plot as — a file name, saved in the plots folder:", suggested);
  if (name === null) return;          // cancelled is not an error
  try {
    await saveTo(name.trim());
  } catch (e) {
    status(e instanceof Error ? e.message : String(e), true);
  }
}

async function save(): Promise<void> {
  if (!savedAs) { await saveAs(); return; }
  try {
    await saveTo(savedAs);
  } catch (e) {
    // ⚠ Say so, and say which file. A save that did not happen and reports
    // nothing is how a day of work goes missing.
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Lay a picture of a plan under the drawing, to trace over.
 *
 *  ⭐ It arrives at a GUESS — as wide as the room — and the designer calibrates
 *  it. Landing it at some arbitrary size and leaving them to find it is the bug
 *  already filed against the DXF import (#63); a backdrop that starts on top of
 *  the room is at worst the wrong size, never invisible.
 */
async function placeBackdrop(file: File, page: number): Promise<void> {
  status("rendering the page…");
  const { href, wIn, hIn } = await pdfRaster(file, page);
  baseImage = {
    href, aspect: hIn / wIn,
    x: 0, y: 0, wide: store.plot.room.width, rotate: 0, opacity: 0.45,
  };
  syncBackdropBar();
  draw();
  status(`Backdrop placed, guessed at ${fmtFt(baseImage.wide)} wide. `
       + `Calibrate it: click two points you know the distance between.`);
  startCalibration();
}

/** Click two points on the backdrop, say how far apart they really are.
 *
 *  ⭐ TWO POINTS, NOT A WIDTH. Nobody knows how many feet across a planner's PDF
 *  "is" — but everybody knows how wide their own stage is, and it is somewhere
 *  in the picture. Calibration asks for the dimension they have, not the one the
 *  file would have to declare.
 */
function startCalibration(): void {
  if (!baseImage) return;      // nothing started, so nothing to stop
  stopPlanModes();
  calibrating = {};
  svg.style.cursor = "crosshair";
}

function stopCalibration(): void {
  calibrating = undefined;
  svg.style.cursor = "";
}

/** A click while calibrating. Returns true if it was consumed. */
function calibrationClick(x: number, y: number): boolean {
  if (!calibrating || !baseImage) return false;
  if (!calibrating.a) {
    calibrating.a = { x, y };
    status("Now click the second point.");
    return true;
  }
  const dx = x - calibrating.a.x, dy = y - calibrating.a.y;
  const drawn = Math.hypot(dx, dy);
  if (drawn < 0.05) { status("Those are the same point — click further apart.", true); return true; }

  const answer = window.prompt(
    `How far apart are those two points, really?\n\n`
    + `They are ${fmtFt(drawn)} apart on the backdrop as it is drawn now.`,
    fmtFt(drawn));
  stopCalibration();
  if (answer === null) { status(""); draw(); return true; }
  const real = parseFeet(answer.trim());
  if (real === null || real === undefined || real <= 0) {
    status(`"${answer}" is not a length — try 24', 24'-6" or 24.5`, true);
    draw(); return true;
  }
  // ⚠ Scale about the image's own corner, so calibrating does not also move it.
  const k = real / drawn;
  baseImage.wide *= k;
  syncBackdropBar();
  draw();
  status(`Backdrop scaled — it is now ${fmtFt(baseImage.wide)} wide. `
       + `Set x and y to put it where it goes. Nothing on it is a measurement.`);
  return true;
}

// --------------------------------------------------- number by clicking
/** Numbering a run by pointing at the units in hanging order.
 *
 *  ⭐ Jerry, 2026.09.30: "pick a starting sequence number and then letting the
 *  user fix the sequence by selecting units."
 *
 *  Same shape as `calibrating` and `drawingPipe` — a mode the PLAN is in, not a
 *  dialog, because the thing being pointed at is the rig. The rules live in
 *  `sequence.ts` so they can be tested without a browser; this is the wiring.
 */
let numbering: Seq | undefined;

function startNumbering(pos: Position, start: number): void {
  stopPlanModes();
  numbering = startSeq(pos.name, start);
  svg.style.cursor = "crosshair";
  const n = runIndices(store.plot.instruments, pos.name).length;
  status(`Click the ${n} unit${n > 1 ? "s" : ""} on ${pos.name} in hanging order. `
       + `Next: ${start}. Escape to stop.`);
}

function stopNumbering(): void {
  if (!numbering) return;
  // ⚠ Report on the way out however the pass ended, including abandoned. A run
  // left half-numbered is the one case that genuinely breaks, and it must not
  // end in silence — see `seqReport`.
  const verdict = seqReport(numbering, store.plot.instruments);
  numbering = undefined;
  svg.style.cursor = "";
  status(verdict, verdict.includes("🔴"));
}

/** A click while numbering. Returns true if it was consumed.
 *
 *  ⚠ Consumed EITHER WAY, including a refusal. A click on the wrong unit must
 *  not fall through and select or drag it — the pointer is in a mode, and the
 *  refusal says why.
 */
function numberingClick(target: Element | null): boolean {
  if (!numbering) return false;
  const hit = target?.closest("[data-index]");
  if (!hit) {
    status(`Click a unit on ${numbering.name}, or Escape to stop.`, true);
    return true;
  }
  const index = Number(hit.getAttribute("data-index"));
  const r = seqClick(numbering, store.plot.instruments, index);
  if (!r.ok) { status(r.why, true); return true; }

  // ⚠ ONE UNDO STEP PER CLICK, deliberately. Jerry, 2026.09.30: "you can't just
  // renumber the units." A misclick in the middle of a run should cost one ⌘Z,
  // not the whole pass.
  store.begin(null);
  const inst = store.plot.instruments[index];
  if (inst) inst.unit = r.to;
  store.commit();
  store.select(index);
  draw(); recompute();

  const line = clickLine(r);
  if (r.last) { stopNumbering(); status(line); } else { status(line); }
  return true;
}

/** The imported vector plan, moved and turned to where the designer put it.
 *  The arithmetic is `placeBase` in geometry.ts, where it is unit-tested. */
function placedBasePaths(): { layer: string; points: [number, number][] }[] | undefined {
  return basePlan?.paths ? placeBase(basePlan.paths, baseXf) : undefined;
}

/** What the exporter needs to draw the same base the screen is showing. */
async function baseForExport(): Promise<Record<string, unknown> | undefined> {
  if (!visibilityOf(store.plot).base) return undefined;
  const out: Record<string, unknown> = {};
  const paths = placedBasePaths();
  if (paths?.length) out.paths = paths;
  if (baseImage) {
    // ⚠ Fetched back out of the object URL rather than kept as base64 all
    // along — holding both would double the memory for every plan tried.
    const blob = await (await fetch(baseImage.href)).blob();
    const buf = new Uint8Array(await blob.arrayBuffer());
    let bin = "";
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]!);
    out.image = btoa(bin);
    out.x = baseImage.x; out.y = baseImage.y;
    out.wide = baseImage.wide; out.tall = baseImage.wide * baseImage.aspect;
    out.rotate = baseImage.rotate; out.opacity = baseImage.opacity;
  }
  return Object.keys(out).length ? out : undefined;
}

/** Point at one end of a pipe, then the other.
 *
 *  🔴 SIX BOXES DESCRIBE A PIPE EXACTLY AND NONE OF THEM IS HOW ANYBODY THINKS
 *  ABOUT ONE. Jerry, 2026.09.30, on the length-and-angle fields: "it's a little
 *  hokey - is there a way to let them pick an end point, then the other
 *  endpoint?" He is right. A tower goes where you point at it.
 *
 *  ⚠ The near end is the FIRST click, so the pipe keeps the end you placed
 *  deliberately — the same rule the Length and Angle boxes follow.
 */
/** End whatever mode the plan is in, before putting it in another one.
 *
 *  🔴 THREE MODES NOW WANT THE SAME CLICKS — calibrating, drawing a pipe, and
 *  numbering a run — and each start used to stop only CALIBRATION. So pressing
 *  "draw" during a numbering pass left both armed: numbering is asked first, so
 *  it ate the clicks while the status said "Click one end of Cat 1". The button
 *  did nothing and said it was working.
 *
 *  ⚠ A numbering pass ended this way still reports, and that report is then
 *  overwritten by the new mode's prompt. That is accepted: the durable signal is
 *  the red duplicate-unit note on the position row, which does not scroll away.
 */
function stopPlanModes(): void {
  stopCalibration();
  stopPipeDraw();
  stopNumbering();
}

function startPipeDraw(pos: Position): void {
  stopPlanModes();
  drawingPipe = { pos };
  svg.style.cursor = "crosshair";
  status(`Click one end of ${pos.name}. Escape to stop.`);
}

function stopPipeDraw(): void {
  drawingPipe = undefined;
  svg.style.cursor = "";
  pipeGhost?.remove();
  pipeGhost = undefined;
}

/** The rubber band between the first click and the pointer.
 *
 *  ⚠ Drawn straight onto the svg rather than through render(), so a redraw of
 *  the plot cannot fight with it and a half-finished pipe never reaches the
 *  plot data. It is removed when the pick ends, however it ends. */
function pipeGhostTo(x: number, y: number): void {
  if (!drawingPipe?.a) return;
  if (!pipeGhost) {
    pipeGhost = document.createElementNS("http://www.w3.org/2000/svg", "line");
    pipeGhost.setAttribute("stroke", "#256948");
    pipeGhost.setAttribute("stroke-width", "2");
    pipeGhost.setAttribute("stroke-dasharray", "6 4");
    pipeGhost.setAttribute("pointer-events", "none");
    svg.appendChild(pipeGhost);
  }
  const v = view();
  const a = toScreen({ x: drawingPipe.a.x, y: drawingPipe.a.y }, v);
  const b = toScreen({ x, y }, v);
  pipeGhost.setAttribute("x1", String(a.x)); pipeGhost.setAttribute("y1", String(a.y));
  pipeGhost.setAttribute("x2", String(b.x)); pipeGhost.setAttribute("y2", String(b.y));
}

/** A click while drawing a pipe. Returns true if it was consumed. */
function pipeDrawClick(x: number, y: number): boolean {
  if (!drawingPipe) return false;
  // Feet to the nearest inch. Sub-inch precision on a light plot is a lie, and
  // interact.ts rounds a dragged instrument the same way.
  const snap = (f: number) => Math.round(f * 12) / 12;
  const px = snap(x), py = snap(y);
  if (!drawingPipe.a) {
    drawingPipe.a = { x: px, y: py };
    status(`Now click the other end of ${drawingPipe.pos.name}.`);
    return true;
  }
  const a = drawingPipe.a;
  const ends = { x1: a.x, y1: a.y, x2: px, y2: py };
  if (lengthOf(ends) < 0.25) {
    status("Those are the same point — click the other end further away.", true);
    return true;
  }
  // ⚠ THE OBJECT WE WERE HANDED, not a lookup by name. See onDrawPipe.
  const pos = drawingPipe.pos;
  const name = pos.name;
  stopPipeDraw();
  // ⚠ Still gone if it was deleted while the pick was open. An object that is
  // no longer in the plot must not be written to — it would edit nothing and
  // report success.
  if (!store.plot.positions.includes(pos)) {
    status(`${name} was deleted.`, true); draw(); return true;
  }
  store.begin(null);
  Object.assign(pos, ends);
  store.commit();
  draw(); recompute();
  status(`${name} is ${fmtFt(lengthOf(ends))} at ${Math.round(angleOf(ends) * 10) / 10}°, `
       + `${runOf(ends)}.`);
  return true;
}

/** Show and fill the backdrop controls, or hide them when there is none.
 *
 *  ⭐ NUMBERS, NOT A DRAG, for the first cut. A drag is the nicer gesture and it
 *  is the next piece of work — but a backdrop you can only shove with a mouse
 *  cannot be aligned to a dimension you actually know, and "x = 2'-6"" can.
 */
function syncBackdropBar(): void {
  const bar = $("bdbar");
  if (!baseImage && !basePlan) { bar.hidden = true; return; }
  bar.hidden = false;
  // ⚠ A vector plan has no width to set and nothing to fade — its lines are
  // drawn at the scenery weight. Those two boxes go away rather than sit there
  // doing nothing, and calibrate goes with them: you scale a photograph, you
  // do not scale a drawing that arrived with its own units.
  const vectorOnly = !baseImage;
  $("bdwhat").textContent = vectorOnly ? "base plan" : "backdrop";
  // ⚠ The labels WRAP their input rather than carry a for=, so hide the label.
  for (const id of ["bdw", "bdo", "bdcal"]) {
    const el = $(id);
    ((el.closest("label") as HTMLElement | null) ?? el).hidden = vectorOnly;
  }
  const b = baseImage ?? baseXf;
  ($<HTMLInputElement>("bdx")).value = fmtFt(b.x);
  ($<HTMLInputElement>("bdy")).value = fmtFt(b.y);
  ($<HTMLInputElement>("bdr")).value = String(b.rotate);
  if (baseImage) {
    ($<HTMLInputElement>("bdw")).value = fmtFt(baseImage.wide);
    ($<HTMLInputElement>("bdo")).value = String(Math.round(baseImage.opacity * 100));
  }
}

function wireBackdropBar(): void {
  const len = (id: string, set: (v: number) => void) => {
    $(id).addEventListener("change", () => {
      if (!baseImage && !basePlan) return;
      const v = parseFeet(($<HTMLInputElement>(id)).value.trim());
      // ⚠ Refuse loudly and put it back, the same as every other length box.
      if (v === null || v === undefined) {
        status(`"${($<HTMLInputElement>(id)).value}" is not a length — try 2'6", 30" or 2.5`, true);
        syncBackdropBar(); return;
      }
      set(v); draw(); syncBackdropBar();
    });
  };
  len("bdx", v => { (baseImage ?? baseXf).x = v; });
  len("bdy", v => { (baseImage ?? baseXf).y = v; });
  len("bdw", v => { if (v > 0) baseImage!.wide = v; });
  $("bdr").addEventListener("input", () => {
    if (!baseImage && !basePlan) return;
    (baseImage ?? baseXf).rotate = Number(($<HTMLInputElement>("bdr")).value) || 0; draw();
  });
  $("bdo").addEventListener("input", () => {
    if (!baseImage) return;
    baseImage.opacity = Number(($<HTMLInputElement>("bdo")).value) / 100; draw();
  });
  $("bdcal").addEventListener("click", () => {
    if (!baseImage) return;
    startCalibration();
    status("Click two points you know the real distance between. Escape to stop.");
  });
  $("bdoff").addEventListener("click", () => {
    if (!baseImage && !basePlan) return;
    clearBase();
    stopCalibration(); syncBackdropBar(); draw(); status("Base plan removed.");
  });
}

/** Keep the Open menu in step with what is actually on disk. */
/** What Open’s menu will show, refreshed when the plots folder changes.
 *
 *  ⚠ Held rather than fetched on click, so pressing Open never waits on the
 *  network — but refreshed after every save, because a menu that caches its
 *  items is a menu that lies about what is on disk. */
let openItems: { label: string; value: string }[] = [];
let sampleItems: { label: string; value: string }[] = [];
let openFolder = "";
let canPickFolder = false;

async function refreshOpenList(): Promise<void> {
  const btn = $("open") as HTMLButtonElement;
  try {
    const { plots, folder, canPickFolder: can } = await listPlots();
    openFolder = folder;
    canPickFolder = can ?? false;
    openItems = plots.map(p => ({
      label: p.show ? `${p.show} — ${p.name}` : p.name, value: p.name,
    }));
    btn.title = `Open a saved plot — ${folder}`;
  } catch (e) {
    // The list is a convenience; failing to fetch it must not stop the editor.
    openItems = [];
    btn.title = e instanceof Error ? e.message : String(e);
  }
  // ⭐ WHAT SHIPPED WITH IT, in its own group at the bottom. A beta tester
  // asked, 2026.09.30, whether there was a way to open the demo file again —
  // there was not. The demo lives in samples/ and this list reads the plots
  // folder, so New put it permanently out of reach.
  //
  // 🔴 A GROUP, not another row. A sample is not the designer's work, and a
  // list that mixes the two invites Save to overwrite something that shipped.
  // The `sample:` prefix is what keeps openPlot from looking for it on the
  // wrong side.
  try {
    const bundled = await samples();
    sampleItems = bundled.map(b => ({
      label: b.show ? `${b.show} — ${b.name}` : b.name,
      value: `sample:${b.name}`,
    }));
  } catch (e) {
    console.warn("samples unavailable:", e);
    sampleItems = [];
  }
}

/** Run one export.
 *
 *  ⭐ Lifted out of the <select>'s change handler when Export became a button.
 *  Jerry, 2026-10-01: "I think the export and open should be a button, just
 *  like save as, and ground plan." The body is unchanged — which options
 *  belong to which kind is the delicate part and was not worth re-deriving.
 */
async function runExport(kind: ExportKind): Promise<void> {
    try {
      // ⚠ Encoded ONCE — the image goes through base64 and a big plan is
      // megabytes of string.
      const exportBase = kind === "pdf" ? await baseForExport() : undefined;
      const vis = visibilityOf(store.plot);
      // ⭐ The PDF is a drawing and honours what the checkboxes are showing:
      // a designer who hides the pools to read the plan expects the print to
      // match. The CSV and patch exports have no drawing in them, so they are
      // sent the plot alone and cannot be changed by a checkbox.
      await exportFile(kind, store.plot, {
        scale: $<HTMLSelectElement>("scale").value,
        // ⚠ The sheet goes with the DRAWINGS only. A CSV has no paper.
        // ⭐ The section is a drawing too, and reads trims off its scale — so it
        // takes the sheet and the scale, and none of the layer options, which
        // are about the plan.
        ...((kind === "pdf" || kind === "section") && $<HTMLSelectElement>("page").value
            ? { page: $<HTMLSelectElement>("page").value } : {}),
        ...(kind === "pdf" ? {
          // ⭐ ONE SOURCE for the screen and the paper. These three were read
          // off the checkboxes while the screen was about to be read off the
          // plot — which is how a PDF comes out showing something the screen
          // was not. The server's field names are unchanged; only where the
          // answer comes from has moved.
          showPools: vis.pools,
          showFocus: vis.focus,
          showLabels: vis.labels,
          ...(poolPlane() === undefined ? {} : { poolPlane: poolPlane() }),
          // ⭐ `rulers` IS the dimensions layer now, which is what retires the
          // special case: it used to be the one display toggle that lived
          // outside the group and printed without drawing.
          rulers: vis.dimensions,
          // 🔴 Until now the import went on the SCREEN and never on the
          // paper. exports.plot_pdf has taken a base plan the whole time and
          // nothing ever handed it one, so an imported venue drawing looked
          // like it had worked right up to the moment you printed it.
          ...(exportBase ? { base: exportBase } : {}),
        } : {}),
      });
      status("");
    } catch (err) {
      // The commonest failure is the sheet refusing to clip, and it says
      // which scale would fit. That belongs in front of the user, not a console.
      status(err instanceof Error ? err.message : String(err), true);
    }
}

/** Open the plots menu under its button. */
function showOpenMenu(): void {
  const btn = $("open") as HTMLButtonElement;
  const groups: MenuGroup[] = [];
  if (openItems.length) {
    groups.push({ items: openItems.map(i => ({
      label: i.label, icon: "description", onSelect: () => void openPlot(i.value),
    })) });
  } else {
    // ⚠ M3: an item that cannot be used is DISABLED, not removed. An empty
    // menu that opens and shows nothing reads as a broken button.
    groups.push({ items: [{ label: "No saved plots yet", disabled: true }] });
  }
  if (sampleItems.length) {
    // 🔴 Its own group, as it was its own optgroup. A sample is not the
    // designer’s work, and a list that mixes the two invites Save to overwrite
    // something that shipped.
    groups.push({ heading: "Comes with plotedit", items: sampleItems.map(i => ({
      label: i.label, icon: "inventory_2",
      // ⚠ A sample opens UNSAVED and UNNAMED, so the first ⌘S asks where to
      // put it rather than writing back over the file that shipped.
      onSelect: () => void openSample(i.value.slice(7)),
    })) });
  }
  // ⭐ WHERE THEY LIVE, AND HOW TO CHANGE IT, at the foot of the list. Jerry,
  // 2026-10-01: "folder picking should work just like ground plan" — a native
  // dialog, which it is, though the server has to be the one to open it. The
  // folder itself stays a disabled item: it is a fact about the list above, not
  // something to click.
  const tail: MenuItem[] = [];
  if (openFolder) tail.push({ label: openFolder, disabled: true, icon: "folder" });
  if (canPickFolder) {
    tail.push({ label: "Change folder…", icon: "folder_open", onSelect: () => void changeFolder() });
  }
  if (tail.length) groups.push({ items: tail });
  openMenu(btn, groups);
}

/** Ask where plots should live, then show what is there.
 *
 *  ⚠ Nothing is sent. The server opens the operating system's dialog and reads
 *  the answer; the browser never handles a path. See `api.pickPlotsFolder`.
 */
async function changeFolder(): Promise<void> {
  try {
    status("Choose a folder — the dialog may be behind this window.");
    const { changed, folder } = await pickPlotsFolder();
    if (!changed) { status(""); return; }
    await refreshOpenList();
    status(`Plots are now kept in ${folder}.`);
  } catch (e) {
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Say what the PDF will print at, in the toolbar, without opening anything.
 *
 *  ⭐ Jerry, 2026-10-01: "where is the scale" — asked right after Sheet and Scale
 *  moved into the Export menu, which is the question answering itself. Moving the
 *  CONTROLS was right; losing the READOUT was not. The toolbar used to display
 *  the scale at all times, so what the plot would print at was ambient. It had
 *  become something you went looking for.
 *
 *  ⚠ Shows the sheet too, because the two are not independent: Fit means "the
 *  largest scale at which nothing runs off the CHOSEN sheet", so a scale without
 *  its sheet is half an answer.
 */
function syncSheetInfo(): void {
  const el = document.getElementById("sheetinfo");
  if (!el) return;
  const label = (sel: HTMLSelectElement) =>
    Array.from(sel.options).find(o => o.value === sel.value)?.textContent ?? sel.value;
  const sheet = label($<HTMLSelectElement>("page"));
  const scale = label($<HTMLSelectElement>("scale"));
  // The sheet's bracketed dimensions are for choosing, not for glancing at.
  const short = sheet.replace(/\s*\(.*\)\s*$/, "");
  el.replaceChildren();
  el.append(short);
  const sep = document.createElement("span");
  sep.className = "sep";
  sep.textContent = " · ";
  el.append(sep, scale);
}

/** One submenu of radio choices, built from a hidden <select>.
 *
 *  ⚠ The SELECT IS THE STATE. `fillPageMenu` and `fillScaleMenu` keep it
 *  unit-correct and carry a fallback that matters — the sheet list's first entry
 *  is the SMALLEST, so defaulting to it would silently issue a D-sized plot on
 *  Letter. Reading the options instead of re-deriving them keeps that care.
 */
function optionsSubmenu(selectId: string, after?: () => void): MenuGroup[] {
  const sel = $<HTMLSelectElement>(selectId);
  return [{ items: Array.from(sel.options).map(o => ({
    label: o.textContent ?? o.value,
    selection: "radio" as const,
    checked: o.value === sel.value,
    onSelect: () => { sel.value = o.value; syncSheetInfo(); after?.(); },
  })) }];
}

/** Open the export menu under its button.
 *
 *  ⭐ Grouped by what it PRODUCES — drawings, paperwork, then the console file —
 *  which is the indent #56 asked for. And Sheet, Scale and Rulers now live HERE,
 *  because the exported PDF is the only thing any of them changes. In the
 *  toolbar they read as app state; the screen drawing has never looked at them.
 */
function showExportMenu(): void {
  const btn = $("export") as HTMLButtonElement;
  const sheet = $<HTMLSelectElement>("page");
  const scale = $<HTMLSelectElement>("scale");
  const chosen = (sel: HTMLSelectElement) =>
    Array.from(sel.options).find(o => o.value === sel.value)?.textContent ?? "";

  openMenu(btn, [
    { items: [
      { label: "Plot PDF", icon: "picture_as_pdf", onSelect: () => void runExport("pdf") },
      // ⭐ #92. The section has existed and worked since the scaffold and could
      // only be reached by typing `python3 plot_to_section.py` at a terminal —
      // which, for an application whose whole premise is that it needs Python
      // and nothing else, meant almost nobody using it had ever seen one.
      //
      // ⚠ It cuts on CENTRELINE and the sheet says so. A section needs a cut
      // line that the plot does not carry; asking before anything can be drawn
      // would be worse than taking the obvious cut and stating it, which §3
      // requires on the sheet anyway.
      { label: "Section", icon: "height", onSelect: () => void runExport("section") },
      { label: "Plot DXF", icon: "architecture", onSelect: () => void runExport("dxf") },
    ] },
    { items: [
      { label: "Instrument schedule", icon: "table_rows", onSelect: () => void runExport("schedule") },
      { label: "Channel hookup", icon: "cable", onSelect: () => void runExport("hookup") },
    ] },
    { items: [
      { label: "Eos patch", trailing: "untested", icon: "memory",
        onSelect: () => void runExport("eos") },
    ] },
    // ⚠ PDF ONLY, and the heading says so. A CSV has no paper, and the DXF
    // carries its own units — offering them a sheet would be a lie.
    { heading: "PDF only", items: [
      { label: "Sheet", icon: "description", trailing: chosen(sheet),
        submenu: optionsSubmenu("page") },
      { label: "Scale", icon: "straighten", trailing: chosen(scale),
        // ⭐ Changing the SHEET can change the SCALE, because Fit means "the
        // largest scale at which nothing runs off the chosen sheet". Showing
        // both here, one under the other, is the first time that has been
        // visible — in the toolbar they looked like independent menus.
        submenu: optionsSubmenu("scale") },
      // ⭐ RULERS IS A LAYER NOW — `dimensions`, one of the eight. It was the
      // last display toggle with its own private checkbox, print-only and
      // outside the group, and docs/LAYERS.md called that out: "rulers stops
      // being a special case. It is print-only because the screen has no
      // Dimensions layer; once it does, it is just a layer that defaults off."
      //
      // ⭐ And it is now SAVED WITH THE PLOT, which it never was. Tick the
      // rulers, reload, and they stayed on your last export only by accident of
      // the page not having been refreshed.
      { label: "Rulers", icon: "straighten", selection: "check",
        checked: visibilityOf(store.plot).dimensions,
        onSelect: () => store.setLayerVisible(
          "dimensions", !visibilityOf(store.plot).dimensions) },
    ] },
  ]);
}

/** Bring in a ground plan from a PDF.
 *
 * ⚠ TWO THINGS A PDF CANNOT TELL US, and both are asked rather than guessed:
 *
 *   THE SCALE. A PDF measures paper — points, 72 to the printed inch. The only
 *   route to feet is the "1/4\" = 1'-0\"" printed in its title block, and
 *   nothing in the file states it in a form anything can read.
 *
 *   WHICH PAGE. A set of drawings is one file; the ground plan is rarely page 1.
 *
 * ⚠ And no layers. A DXF import can take WALLS and leave the title block
 * behind; a PDF is one flat pile of strokes, so the border and every dimension
 * line arrive with the walls. Said out loud rather than discovered.
 */
async function importPdf(file: File): Promise<void> {
  try {
    status("reading the PDF…");
    const { pages, scales } = await pdfPages(file);

    // ⚠ A scanned plan has no vectors at all. Saying so beats importing nothing
    // and looking broken.
    const usable = pages.filter(p => p.items > 0);
    if (!usable.length) {
      // ⭐ NO VECTORS IS NO LONGER A DEAD END. A photograph cannot be traced into
      // geometry, but it can be laid underneath and drawn over — which is what a
      // designer with a planner's layout actually wants.
      const withPics = pages.filter(p => p.images > 0);
      const pg = (withPics[0] ?? pages[0])?.page ?? 1;
      if (!window.confirm(
            `${file.name} has no vector drawing in it, so there is no geometry `
          + `to import.\n\nPlace it as a BACKDROP instead? You can draw over `
          + `it, but nothing can be measured off it — the room size is still `
          + `yours to type in.`)) { status(""); return; }
      await placeBackdrop(file, pg);
      return;
    }

    let page = usable[0]!.page;
    if (usable.length > 1) {
      const list = usable.map(p =>
        `  page ${p.page}: ${p.width_in}" x ${p.height_in}", ${p.items} lines`).join("\n");
      const answer = window.prompt(`${file.name}\n\n${list}\n\nWhich page?`,
                                   String(page));
      if (answer === null) { status(""); return; }
      page = Number(answer);
    }

    const scale = window.prompt(
      `What scale is that drawing?\n\nIt is printed in the title block — a PDF `
      + `does not record it.\n\nOne of: ${scales.join(", ")}`, "1/4");
    if (scale === null) { status(""); return; }

    const got = await pdfPaths(file, page, scale.trim());
    basePlan = got;
    baseXf = { x: 0, y: 0, rotate: 0 };
    const [x0, y0, x1, y1] = got.extents ?? [0, 0, 0, 0];
    // ⚠ Say the size out loud. At the wrong scale this is still a believable
    // drawing, just of a different building — the number is the only way to
    // catch it.
    status(`${got.paths.length} paths at ${scale}" = 1'-0" — `
           + `${(x1 - x0).toFixed(1)}' x ${(y1 - y0).toFixed(1)}' including the sheet border. `
           + `Check that against something you measured.`);
    store.setLayerVisible("base", true);
    syncBackdropBar(); draw();
  } catch (err) {
    status(err instanceof Error ? err.message : String(err), true);
  }
}

/** Ask before throwing away unsaved work. `what` completes "…and lose them?" */
function mayDiscard(what: string): boolean {
  if (!store.dirty) return true;
  return window.confirm(
    `This plot has unsaved changes.\n\n${what} and lose them?`);
}

/** Put a different plot in the editor.
 *
 * ⚠ Shared by Open and New, because both have to do the SAME five things — a
 * fresh store, a fresh subscription, the pointer and keyboard handlers
 * reattached to it, the symbol cache emptied, and a recompute. New was written
 * as a copy of Open first, and copy number three is where one of them quietly
 * stops re-attaching a handler and dragging silently edits the plot you closed.
 */
async function adoptPlot(plot: Plot, savedName: string | null): Promise<void> {
  // 🔴 A DIFFERENT PLOT MEANS A DIFFERENT ROOM. The imported ground plan is not
  // in the file, so without this it survives into whatever you open next — the
  // bug a tester hit on 2026.10.05. Every Open, New and sample load comes
  // through here, which is why it belongs here and not in each of them.
  clearBase();
  // ⚠ paint() does not touch the backdrop bar, so the controls would otherwise
  // keep offering to move and remove a plan that is already gone.
  syncBackdropBar();
  store = new Store(plot);
  // ⭐ WHAT REVERT GOES BACK TO. #56: "save the state before we open it."
  // Cloned, because the store mutates its plot in place and a reference would
  // quietly become the live document.
  onDisk = structuredClone(plot);
  savedAs = savedName;
  store.subscribe(paint);
  attachPointer(svg, store, { view, onChange: draw, onSettled: () => recompute() });
  attachKeyboard(store, { view, onChange: draw, onSettled: () => recompute() });
  symbolCache = {};
  await recompute(0);
}

async function openPlot(name: string): Promise<void> {
  if (!mayDiscard("Open a different plot")) return;
  try {
    await adoptPlot(await loadPlot(name), name);
    status(`Opened ${name}`);
  } catch (e) {
    status(e instanceof Error ? e.message : String(e), true);
  }
}

/** Open one of the plots that shipped with the program.
 *
 *  ⭐ ADOPTED WITH NO NAME. `savedAs` stays null, so the first Save asks where
 *  to put it rather than writing back over the sample — a designer who opens
 *  the demo to look at it should not be able to destroy it by pressing ⌘S.
 */
async function openSample(name: string): Promise<void> {
  if (!mayDiscard("Open the demo plot")) return;
  try {
    await adoptPlot(await readSample(name), null);
    status(`Opened ${name} — a copy. Save As… to keep your changes.`);
  } catch (e) {
    status(e instanceof Error ? e.message : String(e), true);
  }
}

async function newFile(): Promise<void> {
  if (!mayDiscard("Start a new plot")) return;
  const show = window.prompt("What is the show called?", "Untitled");
  if (show === null) return;                 // cancelled is not an error
  // ⚠ savedAs is null, so the first Save ASKS where to put it rather than
  // overwriting whatever was open a moment ago.
  await adoptPlot(newPlot(show.trim() || "Untitled"), null);
  // ⚠ AND OPEN IT, because the line below sends the reader there. Show & Venue
  // starts CLOSED now (#56), which is right for a plot that already has a room —
  // but a brand new one has nothing else to do first, and an instruction that
  // points at a collapsed panel is worse than no instruction.
  const venue = document.getElementById("panel-details") as HTMLDetailsElement | null;
  if (venue) venue.open = true;
  status("New plot — set the room and the venue in Show & Venue, "
         + "then add a position.");
}

function status(msg: string, bad = false) {
  const el = $("status");
  el.textContent = msg;
  el.className = bad ? "warn" : "muted";
}

function showError(e: unknown) {
  const box = $("err");
  box.hidden = false;
  box.textContent = `${e instanceof Error ? e.message : String(e)}

Is the Python service running?
    cd server && uvicorn plotedit.api:app --reload`;
}

/** Show which build this is, beside the show name.
 *
 * ⚠ Never blocks boot and never invents a number. If the server cannot be
 * asked, the slot says so — a working copy reporting itself as a release sends
 * whoever reads a bug report hunting in source that was not running. */
async function showVersion(): Promise<void> {
  const el = $("version");
  const v = await serverVersion();
  const known = v !== "dev" && v !== "unknown";
  el.textContent = known ? `v${v}` : (v === "dev" ? "dev build" : "version unknown");
  el.classList.toggle("dev", !known);
}

async function boot() {
  void showVersion();
  try {
    // ⭐ Open what you were last working on. Starting on the bundled sample
    // every time means a designer's first act at every session is to find their
    // own plot again — and, for anyone who has just downloaded this, it means
    // their work disappears the moment they reload.
    let opened: Plot | null = null;
    try {
      const { plots } = await listPlots();          // newest first
      const newest = plots[0];
      if (newest) {
        opened = await loadPlot(newest.name);
        savedAs = newest.name;
      }
    } catch {
      // No server answer, or no plots folder yet. The sample below is a fine
      // first screen; it is not worth refusing to start over.
    }

    if (!opened) {
      // ⚠ The DEMO, not the test fixture. server/testdata/blackbox.plot.json is
      // what the suites assert against — it lives outside the public dir on
      // purpose, so it is not served and does not ship in the download.
      // demo.plot.json is the one a stranger should meet first.
      const r = await fetch("/demo.plot.json");
      if (!r.ok) throw new Error(`cannot load the demo plot: ${r.status}`);
      const json: unknown = await r.json();
      if (!isPlot(json)) throw new Error("that file is not a plot (formatVersion must be 1)");
      opened = json as Plot;
    }

    store = new Store(opened);
    // 🔴 THE SECOND PLACE A STORE IS BORN. `adoptPlot` handles Open and New and
    // sets `onDisk` there; startup builds its own and did not, so Revert sat
    // disabled for the whole session on the plot you actually opened the app
    // with. Found by pressing it: the plot went dirty, Save lit up, and Revert
    // did not — because `!onDisk` was still true.
    onDisk = structuredClone(opened);
    fixtureTable = await fixtures();
    // ⚠ Not fatal. A missing DMX table means the Model and personality lists
    // come up empty; it must not stop the editor opening a plot.
    try {
      dmxTable_ = await dmxTable();
    } catch (e) {
      console.warn("DMX personalities unavailable:", e);
    }
    // ⚠ Also not fatal. Without it the Color box is a plain text field, which
    // is exactly what it was before the suggestions existed.
    try {
      gelList_ = await gelList();
    } catch (e) {
      console.warn("gel suggestions unavailable:", e);
    }
    // ⚠ Not fatal either. Without it the sheet menu shows ARCH D and the export
    // sends no page, which is exactly what it did before the menu existed.
    try {
      paperSizes_ = await paperSizes();
      fillPageMenu();
    } catch (e) {
      console.warn("paper sizes unavailable:", e);
    }

    paintChrome();
    // ⚠ The room's provenance and the plot notes are not shown in the app at
    // all — not as a block, not as a tooltip. Jerry, 2026.09.24: "lose it."
    // The PDF still prints the room's source across the top of the drawing,
    // which is the copy that leaves the building.

    store.subscribe(paint);
    attachPointer(svg, store, { view, onChange: draw, onSettled: () => recompute() });
    attachKeyboard(store, { view, onChange: draw, onSettled: () => recompute() });

    // ⚠ poolplane is NOT in this list — it changes the NUMBERS, not just what is
    // shown, so it has to recompute rather than redraw. Wired separately below;
    // adding it here would have moved the picker and left the pools unchanged.
    //
    // ⚠ `rulers` is not here either, for the opposite reason: it changes the
    // PRINT and nothing on screen. Wiring it to draw would redraw the canvas
    // to no visible effect and suggest the toggle had failed.
    for (const id of ["zoom"])
      $(id).addEventListener("input", draw);

    // ⭐ A CHIP IS AN EDIT NOW, so it goes through the store: it is undoable,
    // it marks the plot unsaved, and it is saved with the file. That last part
    // is the point — reopen the plot and the layers are as you left them.
    //
    // ⚠ No `draw()` here. The store emits, paint() runs, and paint() both
    // syncs the chips and redraws. Calling draw() as well would draw twice and,
    // worse, would make the chip look as though it worked even if the store had
    // refused the change.
    for (const l of SCREEN_LAYERS)
      $(`layer-${l.id}`).addEventListener("input", (e) => {
        store.setLayerVisible(l.id, (e.target as HTMLInputElement).checked);
      });
    $("poolplane").addEventListener("change", () => { void recompute(); });

    // ⭐ `at …` belongs to `pools`, not to the row. When pools is off it has
    // nothing to say, so it goes INERT — greyed and unclickable — rather than
    // disappearing. DECISIONS.md, "Fields that do not apply go inert, not
    // hidden": a control that vanishes takes its explanation with it, and the
    // reader is left wondering where the height went.
    const syncPoolPlane = () => {
      const on = visibilityOf(store.plot).pools;
      $("poolplane-label").classList.toggle("inert", !on);
      ($("poolplane") as HTMLSelectElement).disabled = !on;
    };
    // ⚠ Subscribed rather than hung off the checkbox: pools can now be turned
    // off by an undo, and the height picker has to go inert for that too.
    store.subscribe(syncPoolPlane);
    syncPoolPlane();

    // ---- export
    // ⭐ BUTTONS THAT OPEN MENUS. Both were <select>s whose change handler fired
    // an action and then set `sel.value = ""` — a control that clears itself
    // after every use was never holding a value. See menu.ts.
    $("export").addEventListener("click", () => showExportMenu());
    $("open").addEventListener("click", () => showOpenMenu());
    // ⚠ Anchored to the EXPORT button, not to itself, so the menu lands where it
    // does from every other route. A menu that moves depending on which of two
    // things you pressed is a menu you have to look for twice.
    $("sheetinfo").addEventListener("click", () => showExportMenu());

    $("revert").addEventListener("click", () => {
      if (!onDisk || !store.dirty) return;
      if (!confirmRevert(savedAs)) return;
      store.revertTo(onDisk);
      // ⚠ The same four things every other plot-level change does. A revert that
      // restored the data and left the drawing, the levels and the chrome stale
      // would look like it had half worked.
      symbolCache = {};
      draw(); recompute(); paintChrome();
      status(savedAs ? `${savedAs} reloaded from disk.`
                     : "Back to the plot as you opened it.");
    });

    // ---- import a venue ground plan
    $("dxf").addEventListener("change", async (e) => {
      const input = e.target as HTMLInputElement;
      const file = input.files?.[0];
      input.value = "";
      if (!file) return;
      // ⭐ Jerry, 2026.09.24: "could we do the same for PDFs too?" A PDF is what
      // comes back when you ask a house for its plan — it is what their drawing
      // office exports for everybody. Same button, because to the reader it is
      // the same act: here is the room, draw it underneath.
      if (file.name.toLowerCase().endsWith(".pdf")) { await importPdf(file); return; }
      try {
        status("reading the DXF…");
        const info = await dxfLayers(file);
        const names = info.layers.map(l => `${l.name} (${l.entities})`).join(", ");
        const want = prompt(
          `${file.name}\nUnits declared: ${info.units}\nLayers: ${names}\n\n` +
          `Which layers? Comma-separated, or blank for all.`, "");
        if (want === null) { status(""); return; }
        const units = info.units === "unitless"
          ? prompt("The file declares no units. in / ft / mm / cm / m?", "in") ?? undefined
          : undefined;
        basePlan = await dxfPaths(file, want ? want.split(",").map(s => s.trim()) : undefined, units);
        baseXf = { x: 0, y: 0, rotate: 0 };
        const [x0, y0, x1, y1] = basePlan.extents ?? [0, 0, 0, 0];
        // Unit headers lie. Say the size out loud so it can be checked against
        // a dimension that is actually known.
        status(`imported ${basePlan.paths.length} paths, ` +
               `${(x1 - x0).toFixed(1)}' x ${(y1 - y0).toFixed(1)}' — check that against something you measured`);
        store.setLayerVisible("base", true);
        syncBackdropBar(); draw();
      } catch (err) {
        status(err instanceof Error ? err.message : String(err), true);
      }
    });
    $("undo").addEventListener("click", () => { store.undo(); recompute(); });
    $("redo").addEventListener("click", () => { store.redo(); recompute(); });
    $("new").addEventListener("click", () => void newFile());
    $("save").addEventListener("click", () => void save());
    $("saveas").addEventListener("click", () => void saveAs());
    // ⭐ CALIBRATION CLICKS GO FIRST, in the CAPTURE phase, so a click meant for
    // the backdrop never also grabs an instrument underneath it. Dragging a
    // light by accident while measuring a wall is the kind of thing that makes
    // somebody stop trusting a tool.
    svg.addEventListener("pointerdown", (e) => {
      if (!calibrating && !numbering && !drawingPipe) return;
      // ⚠ Numbering is asked FIRST and by TARGET, not by coordinate. It picks a
      // unit out of the app's own hit regions, which is what makes a unit in the
      // boom ELEVATION clickable too — on a boom that diagram is where you would
      // naturally point along the run.
      //
      // ⭐ Asking it before the two COORDINATE modes is also what keeps them
      // apart: numbering wants the thing under the pointer, while calibrating
      // and drawing a pipe want the point itself. Only one mode is ever live —
      // each start function stops the others — so the order settles nothing
      // more than which question is cheapest to answer.
      if (numberingClick(e.target as Element | null)) {
        e.preventDefault(); e.stopPropagation(); return;
      }
      const r = svg.getBoundingClientRect();
      const pt = toPlot({ x: e.clientX - r.left, y: e.clientY - r.top }, view());
      if (calibrationClick(pt.x, pt.y) || pipeDrawClick(pt.x, pt.y)) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, true);
    // ⭐ The rubber band. Without it you are clicking twice into nothing and
    // hoping — which is the difference between pointing at a pipe and guessing
    // where its far end will land.
    svg.addEventListener("pointermove", (e) => {
      if (!drawingPipe?.a) return;
      const r = svg.getBoundingClientRect();
      const pt = toPlot({ x: e.clientX - r.left, y: e.clientY - r.top }, view());
      pipeGhostTo(pt.x, pt.y);
      const ends = { x1: drawingPipe.a.x, y1: drawingPipe.a.y, x2: pt.x, y2: pt.y };
      status(`${drawingPipe.pos.name}: ${fmtFt(lengthOf(ends))} at `
           + `${Math.round(angleOf(ends) * 10) / 10}°`);
    });
    // Escape abandons it rather than leaving the cursor a crosshair for ever.
    window.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (calibrating) { stopCalibration(); status(""); }
      if (drawingPipe) { stopPipeDraw(); status(""); }
      // ⚠ Numbering LAST, and it does not clear the status — `stopNumbering`
      // writes its own verdict there, and an empty status would throw away the
      // report on an abandoned pass.
      if (numbering) stopNumbering();
    });

    wireBackdropBar();
    wirePanels();
    wireSplitter();
    wireZoomButtons();
    void refreshOpenList();
    // ⌘S saves, ⇧⌘S saves as. The browser's own Save-page dialog is not what
    // anyone means by ⌘S with a plot open.
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (e.shiftKey) { void saveAs(); return; }
        // ⚠ The shortcut follows the button. A disabled Save whose ⌘S still
        // writes the file is two answers to one question — and saying nothing
        // would read as a save that silently failed, which is worse than both.
        if (!store.dirty) { status("No changes to save."); return; }
        void save();
      }
    });
    window.addEventListener("beforeunload", (e) => {
      if (store.dirty) { e.preventDefault(); e.returnValue = ""; }
    });

    computed = await compute(store.plot, poolPlane());
    await ensureSymbols();
    await ensureBooms();
    await ensureLabels();
    paint();
  } catch (e) {
    showError(e);
  }
}

boot();
