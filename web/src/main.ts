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
import { fitView, fohExtent, setUnitSystem, type View } from "./geometry.js";
import { isPlot, symbolKey, plotFileName, newPlot, type Plot } from "./plot.js";
import { render, POS_CHAR_W, POS_TEXT, type Computed, type RenderOptions } from "./render.js";
import { compute, fixtures, exportFile, dxfLayers, dxfPaths, symbols, booms,
         positionLabels, savePlot, listPlots, loadPlot, pdfPages, pdfPaths,
         serverVersion,
         type FixtureRow, type ExportKind, type DxfPaths, type SymbolPrim,
         type BoomElevation, type PositionLabel } from "./api.js";
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
let basePlan: DxfPaths | null = null;
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
    showPools: $<HTMLInputElement>("pools").checked,
    showFocus: $<HTMLInputElement>("focus").checked,
    showLabels: $<HTMLInputElement>("labels").checked,
    selected: store.selected,
    basePaths: $<HTMLInputElement>("base").checked ? basePlan?.paths : undefined,
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

function draw() {
  // ⚠ Before ANYTHING is formatted. The system is ambient (see geometry.ts) and
  // this is the single place it is refreshed — a draw that ran with a stale one
  // would label a metric plot in feet and look like a conversion bug rather
  // than a missing assignment.
  setUnitSystem(store.plot.units);
  fillScaleMenu(); render(svg, store.plot, view(), computed, opts()); }

function fillTable() {
  const tb = $<HTMLTableElement>("schedule").querySelector("tbody")!;
  tb.replaceChildren();
  store.plot.instruments.forEach((inst, i) => {
    const c = computed[i];
    const tr = document.createElement("tr");
    tr.dataset.index = String(i);
    if (i === store.selected) tr.classList.add("sel");
    const cells: [string, boolean][] = [
      [inst.position ?? "", false], [String(inst.unit), false],
      [inst.channel !== undefined ? String(inst.channel) : "", false],
      [inst.type, false], [inst.color ?? "—", false],
      // ⚠ UNKNOWN, never a blank. An empty cell in a load column reads as
      // "nothing on that circuit", which is how a dimmer gets loaded past its
      // rating on paper.
      [c ? (c.watts != null ? `${c.watts}` : "UNKNOWN") : "—", true],
      [c?.throw_ft ?? "—", true], [c?.field_ft ?? "—", true],
      [c?.footcandles != null ? String(c.footcandles) : "—", true],
    ];
    for (const [text, num] of cells) {
      const td = document.createElement("td");
      if (num) td.className = "num";
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
  });
  renderInspector($("inspector"), store, computed, {
    fixtures: Object.keys(fixtureTable).sort(),
    lamps: ["HPL 750", "HPL 575", "HPL 575X"],
    modes: ["Boost Full", "Regulated Full", "Regulated 3200K", "Regulated 5600K"],
    onStatus: (msg, bad) => status(msg, bad),
    onPhotometricChange: () => { paint(); recompute(); },
    onPaperworkChange: () => paint(),
  });
}

/** Redraw everything from current state. Cheap — no network. */
function paint() {
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

function plotJson(): string {
  return JSON.stringify(store.plot, null, 2);
}

async function saveTo(name: string): Promise<void> {
  const { path } = await savePlot(name, store.plot);
  savedAs = name;
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

/** Keep the Open menu in step with what is actually on disk. */
async function refreshOpenList(): Promise<void> {
  const sel = $("open") as HTMLSelectElement;
  try {
    const { plots, folder } = await listPlots();
    sel.replaceChildren();
    const head = document.createElement("option");
    head.value = ""; head.textContent = plots.length ? "Open…" : "Open… (none saved yet)";
    sel.appendChild(head);
    for (const p of plots) {
      const o = document.createElement("option");
      o.value = p.name;
      o.textContent = p.show ? `${p.show} — ${p.name}` : p.name;
      sel.appendChild(o);
    }
    sel.title = `Plots in ${folder}`;
  } catch (e) {
    // The list is a convenience; failing to fetch it must not stop the editor.
    sel.title = e instanceof Error ? e.message : String(e);
  }
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
      status(`${file.name} has no vector drawing in it — if the plan is a scan `
             + `there is nothing to import`, true);
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
    const [x0, y0, x1, y1] = got.extents ?? [0, 0, 0, 0];
    // ⚠ Say the size out loud. At the wrong scale this is still a believable
    // drawing, just of a different building — the number is the only way to
    // catch it.
    status(`${got.paths.length} paths at ${scale}" = 1'-0" — `
           + `${(x1 - x0).toFixed(1)}' x ${(y1 - y0).toFixed(1)}' including the sheet border. `
           + `Check that against something you measured.`);
    ($("base") as HTMLInputElement).checked = true;
    draw();
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
  store = new Store(plot);
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

async function newFile(): Promise<void> {
  if (!mayDiscard("Start a new plot")) return;
  const show = window.prompt("What is the show called?", "Untitled");
  if (show === null) return;                 // cancelled is not an error
  // ⚠ savedAs is null, so the first Save ASKS where to put it rather than
  // overwriting whatever was open a moment ago.
  await adoptPlot(newPlot(show.trim() || "Untitled"), null);
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
      // ⚠ The DEMO, not the test fixture. samples/bluver.plot.json is what the
      // suites assert against and it is labelled "test data, not a design";
      // demo.plot.json is the one a stranger should meet first.
      const r = await fetch("/demo.plot.json");
      if (!r.ok) throw new Error(`cannot load the demo plot: ${r.status}`);
      const json: unknown = await r.json();
      if (!isPlot(json)) throw new Error("that file is not a plot (formatVersion must be 1)");
      opened = json as Plot;
    }

    store = new Store(opened);
    fixtureTable = await fixtures();

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
    for (const id of ["pools", "focus", "labels", "base", "zoom"])
      $(id).addEventListener("input", draw);
    $("poolplane").addEventListener("change", () => { void recompute(); });

    // ---- export
    $("export").addEventListener("change", async (e) => {
      const sel = e.target as HTMLSelectElement;
      const kind = sel.value as ExportKind;
      sel.value = "";
      if (!kind) return;
      try {
        // ⭐ The PDF is a drawing and honours what the checkboxes are showing:
        // a designer who hides the pools to read the plan expects the print to
        // match. The CSV and patch exports have no drawing in them, so they are
        // sent the plot alone and cannot be changed by a checkbox.
        await exportFile(kind, store.plot, {
          scale: $<HTMLSelectElement>("scale").value,
          ...(kind === "pdf" ? {
            showPools: $<HTMLInputElement>("pools").checked,
            showFocus: $<HTMLInputElement>("focus").checked,
            showLabels: $<HTMLInputElement>("labels").checked,
            ...(poolPlane() === undefined ? {} : { poolPlane: poolPlane() }),
            rulers: $<HTMLInputElement>("rulers").checked,
          } : {}),
        });
        status("");
      } catch (err) {
        // The commonest failure is the sheet refusing to clip, and it says
        // which scale would fit. That belongs in front of the user, not a console.
        status(err instanceof Error ? err.message : String(err), true);
      }
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
        const [x0, y0, x1, y1] = basePlan.extents ?? [0, 0, 0, 0];
        // Unit headers lie. Say the size out loud so it can be checked against
        // a dimension that is actually known.
        status(`imported ${basePlan.paths.length} paths, ` +
               `${(x1 - x0).toFixed(1)}' x ${(y1 - y0).toFixed(1)}' — check that against something you measured`);
        $<HTMLInputElement>("base").checked = true;
        draw();
      } catch (err) {
        status(err instanceof Error ? err.message : String(err), true);
      }
    });
    $("undo").addEventListener("click", () => { store.undo(); recompute(); });
    $("redo").addEventListener("click", () => { store.redo(); recompute(); });
    $("new").addEventListener("click", () => void newFile());
    $("save").addEventListener("click", () => void save());
    $("saveas").addEventListener("click", () => void saveAs());
    $("open").addEventListener("change", (e) => {
      const sel = e.target as HTMLSelectElement;
      const name = sel.value;
      sel.value = "";
      if (name) void openPlot(name);
    });
    wirePanels();
    wireSplitter();
    wireZoomButtons();
    void refreshOpenList();
    // ⌘S saves, ⇧⌘S saves as. The browser's own Save-page dialog is not what
    // anyone means by ⌘S with a plot open.
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void (e.shiftKey ? saveAs() : save());
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
