/** Talk to the Python. Vite proxies /api to localhost:8000. */
import type { Plot, Position, Instrument } from "./plot.js";
import type { Computed } from "./render.js";

/** The colour label's height in feet, as render.ts draws it (TEXT * 0.5). ⚠ If
 *  that changes, this changes with it, or the server works out tiers for a label
 *  size the screen is not using. */
export const COLOR_TEXT_FT = 0.5;

export async function compute(plot: Plot, poolPlane?: number): Promise<Computed[]> {
  const instruments = plot.instruments.map(i => ({
    unit: i.unit, channel: i.channel, type: i.type, x: i.x, y: i.y,
    trim: i.trim, focus_x: i.focusX, focus_y: i.focusY, focus_h: i.focusH ?? 5.5,
    color: i.color, lamp: i.lamp, mode: i.mode,
    position: i.position, purpose: i.purpose,
    // ⚠ THIS LIST IS EXPLICIT, so a field that is not named here does not reach
    // the server at all. The patch column came back "not patched to anything"
    // for a plot where every unit had an address, because address, dimmer and
    // profile were simply never sent — and the server was right about what it
    // was given. Anything /compute has to reason about belongs in this list.
    address: i.address, dimmer: i.dimmer, profile: i.profile, model: i.model,
  }));
  const r = await fetch("/api/compute", {
    method: "POST",
    headers: { "content-type": "application/json" },
    // pool_plane is the height to cut the pools at — the deck, a face, the top
    // of a head. Separate from where each unit is AIMED.
    // ⚠ `units` decides how the server FORMATS its answers — throw_ft, field_ft
    // and the rest come back as text. The arithmetic is feet either way; leave
    // this out and a metric plot gets metric pools beside imperial throws.
    // ⚠ The colour label is drawn at 0.5 FEET on screen, so it scales with the
    // drawing. The sheet draws 7pt, which is a different number of feet at every
    // scale. Telling the server which one we are lets it answer with tiers that
    // are right for THIS drawing — see labels.color_tiers.
    body: JSON.stringify({ instruments, pool_plane: poolPlane, units: plot.units,
                           colorTextHeightFt: COLOR_TEXT_FT }),
  });
  if (!r.ok) throw new Error(`compute failed: ${r.status} ${await r.text()}`);
  return (await r.json()).instruments as Computed[];
}

export interface FixtureRow {
  field: number | null; beam: number | null; candela: number | null;
  reference_lamp: string; family: string; modes: string[] | null; source: string;
}

/** One sheet a plot can be issued on. */
export interface PaperSize { name: string; w_in: number; h_in: number; label: string }

/** The sheets, split by measuring system.
 *
 *  ⚠ ASKED FOR, never typed here. A second copy of the table in TypeScript is
 *  exactly how the lamp dropdown ended a release behind LAMP_MF. */
export async function paperSizes(): Promise<{
  imperial: PaperSize[]; metric: PaperSize[]; default: string;
}> {
  const r = await fetch("/api/pages");
  if (!r.ok) throw new Error(`cannot load the paper sizes: ${r.status}`);
  return r.json();
}

/** The plots bundled with the program, kept apart from the designer's own. */
export async function samples(): Promise<{ name: string; show: string }[]> {
  const r = await fetch("/api/samples");
  if (!r.ok) throw new Error(`cannot list the samples: ${r.status}`);
  return (await r.json()).samples;
}

export async function readSample(name: string): Promise<Plot> {
  const r = await fetch(`/api/samples/${encodeURIComponent(name)}`);
  if (!r.ok) throw new Error(`cannot open ${name}: ${r.status}`);
  return (await r.json()).plot as Plot;
}

/** One page of a PDF as a picture, for a plan with no vectors in it.
 *
 *  ⭐ A photograph of a room cannot be traced into geometry — tracing it would
 *  invent walls. It CAN be a backdrop to draw over, which is what this is for.
 *  🔴 The result is never a measurement. See the endpoint.
 */
export async function pdfRaster(
  file: File, page: number,
): Promise<{ href: string; wIn: number; hIn: number }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("page", String(page));
  const r = await fetch("/api/import/pdf/raster", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text() || `raster failed: ${r.status}`);
  const blob = await r.blob();
  return {
    href: URL.createObjectURL(blob),
    wIn: Number(r.headers.get("X-Page-Width-In") ?? 0),
    hIn: Number(r.headers.get("X-Page-Height-In") ?? 0),
  };
}

/** The fixture table, so the inspector can offer real types rather than free text. */
export async function fixtures(): Promise<Record<string, FixtureRow>> {
  const r = await fetch("/api/fixtures");
  if (!r.ok) throw new Error(`fixtures failed: ${r.status}`);
  return (await r.json()).fixtures as Record<string, FixtureRow>;
}

/** Gel numbers and names, for the colour suggestions.
 *
 *  ⚠ Numbers only as the VALUE. The table is keyed on "R52", and a name in the
 *  value would match nothing. The name is the label the browser shows beside
 *  it. */
export async function gelList(): Promise<{ gel: string; name: string }[]> {
  const r = await fetch("/api/gels");
  if (!r.ok) throw new Error(`gels failed: ${r.status}`);
  const gels = (await r.json()).gels as Record<string, { name: string }>;
  return Object.entries(gels)
    .map(([gel, v]) => ({ gel, name: v.name }))
    .sort((a, b) => a.gel.localeCompare(b.gel, undefined, { numeric: true }));
}

// ------------------------------------------------------------------ export

export type ExportKind = "pdf" | "dxf" | "schedule" | "hookup" | "eos";

/** Ask the server for a file and hand it to the browser as a download. */
export interface ExportOptions {
  scale?: string;
  /** The sheet, e.g. "ARCH_D" or "A1". Omitted means the server's default —
   *  which is what every export did until a tester asked for something bigger
   *  than ARCH D and found there was no way to say so. */
  page?: string;
  landscape?: boolean;
  /** What the plan/pools/focus/labels checkboxes are showing. Sent so the
   *  print matches the screen; omitted entirely for the CSV and patch exports,
   *  which have no drawing to hide. */
  showPools?: boolean;
  showFocus?: boolean;
  showLabels?: boolean;
  /** The height the pools are cut at, in feet. */
  poolPlane?: number;
  /** Print a dimension scale along the plan's edges. PDF only — the browser
   *  does not draw them. */
  rulers?: boolean;
  /** The imported base plan, already placed in stage feet — `paths`, and an
   *  `image` as base64 PNG with its rectangle. ⚠ Sent as DRAWN rather than as
   *  imported, so the server does not redo the placement arithmetic. Two copies
   *  of it is exactly how the screen and the paper drift apart. */
  base?: Record<string, unknown>;
}

export async function exportFile(
  kind: ExportKind, plot: Plot, opts: ExportOptions = {},
): Promise<void> {
  const r = await fetch(`/api/export/${kind}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    // ⚠ Send only what was CHOSEN. Repeating the defaults here meant the
    // client silently overrode the server's — the page and orientation moved to
    // ARCH D landscape and every export still came out tabloid portrait.
    body: JSON.stringify({
      plot,
      ...(opts.scale ? { scale: opts.scale } : {}),
      ...(opts.page ? { page: opts.page } : {}),
      ...(opts.landscape === undefined ? {} : { landscape: opts.landscape }),
      ...(opts.showPools === undefined ? {} : { showPools: opts.showPools }),
      ...(opts.showFocus === undefined ? {} : { showFocus: opts.showFocus }),
      ...(opts.showLabels === undefined ? {} : { showLabels: opts.showLabels }),
      ...(opts.poolPlane === undefined ? {} : { poolPlane: opts.poolPlane }),
      ...(opts.rulers ? { rulers: true } : {}),
      ...(opts.base ? { base: opts.base } : {}),
    }),
  });
  if (!r.ok) {
    // 422 is the sheet refusing to clip — it names the scale that would fit.
    const detail = await r.json().then(j => j.detail).catch(() => r.statusText);
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await r.blob();
  const name = filenameFrom(r.headers.get("content-disposition")) ?? `${kind}`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** RFC 5987: prefer filename*, fall back to the ASCII filename. */
function filenameFrom(disposition: string | null): string | null {
  if (!disposition) return null;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (star?.[1]) return decodeURIComponent(star[1]);
  const plain = /filename="([^"]+)"/i.exec(disposition);
  return plain?.[1] ?? null;
}

// ------------------------------------------------------------------ import

export interface DxfLayers {
  units: string;
  layers: { name: string; entities: number }[];
}

export interface DxfPaths {
  units: string;
  units_from: string;
  layers: string[];
  extents: [number, number, number, number] | null;
  paths: { layer: string; points: [number, number][] }[];
  truncated: boolean;
}

export async function dxfLayers(file: File): Promise<DxfLayers> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/import/dxf/layers", { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

export async function dxfPaths(
  file: File, layers?: string[], units?: string,
): Promise<DxfPaths> {
  const fd = new FormData();
  fd.append("file", file);
  if (layers?.length) fd.append("layers", layers.join(","));
  if (units) fd.append("units", units);
  const r = await fetch("/api/import/dxf", { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
  return r.json();
}

// ------------------------------------------------------------------ symbols

export type SymbolPrim =
  | { k: "poly"; pts: [number, number][]; closed: boolean }
  | { k: "line"; a: [number, number]; b: [number, number] }
  | { k: "circle"; c: [number, number]; r: number; dashed: boolean; filled: boolean }
  | { k: "text"; c: [number, number]; s: string; size: number };

/** RP-2 symbol outlines, fetched rather than reimplemented.
 *  The geometry lives once, in symbols.py, so the screen and the paper cannot
 *  drift apart the way the photometrics did before test_agreement.py existed. */
export async function symbols(
  types: string[], lensRotation?: number,
): Promise<Record<string, SymbolPrim[]>> {
  const want = [...new Set(types)].filter(Boolean);
  if (!want.length) return {};
  const rot = lensRotation === undefined ? "" : `&lens_rotation=${lensRotation}`;
  const r = await fetch(`/api/symbols?types=${encodeURIComponent(want.join(","))}${rot}`);
  if (!r.ok) throw new Error(`symbols failed: ${r.status}`);
  return (await r.json()).symbols as Record<string, SymbolPrim[]>;
}

/** Renumber the units on one position, per RP-2 §2.3.2.
 *
 * ⚠ Returns what the numbers WOULD be. It does not apply them — on a plot that
 * has been hung, a renumber produces a different document from the one taped to
 * the pipe, so the caller has to mean it.
 */
export async function renumber(
  plot: Plot, position: Position,
): Promise<{
  instruments: Instrument[]; count: number; changed: number;
  moves: { from: number; to: number; x?: number; y?: number; height?: number }[];
  convention: string; warning: string | null;
}> {
  const name = position.name.trim().toLowerCase();
  const on = plot.instruments.filter(
    i => (i.position ?? "").trim().toLowerCase() === name);
  const r = await fetch("/api/renumber", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ instruments: on, position }),
  });
  if (!r.ok) throw new Error(`renumber failed: ${r.status} ${await r.text()}`);
  return r.json();
}

/** One boom drawn in ELEVATION beside the plot, per RP-2 §6.12.
 *
 * ⭐ In PLAN a boom is a POINT: every unit on it shares one x and one y and
 * differs only in height. The browser used to draw them all at that point, so
 * three units and three channel circles landed on one spot.
 *
 * ⚠ The layout is NOT computed here. `dy` and `breaks` come from booms.py, the
 * same call the PDF makes, because the compression is a drawing decision and
 * two copies of it would drift. `height`/`label` are the REAL trim — the break
 * marks say the paper is short, never that a number is approximate.
 */
export interface BoomUnit {
  unit: number; channel?: number; type: string; color?: string;
  accessories?: string[];
  height: number; label: string; dy: number;
  /** This unit's OWN outline, accessories included — not a cache lookup by
   *  bare type, which would draw it without its top hat. */
  prims: SymbolPrim[];
}
export interface BoomElevation {
  name: string;
  x: number; y: number;
  unit_gap: number;
  top: number;
  breaks: number[];
  units: BoomUnit[];
  no_height: { unit: number; type: string }[];
  plan: {
    x: number; y: number; rotation: number; mount: string; width: number;
    type: string; prims: SymbolPrim[]; hatch: SymbolPrim[];
  };
}

export async function booms(plot: Plot): Promise<{ booms: BoomElevation[]; space: number }> {
  const r = await fetch("/api/booms", {
    method: "POST", headers: { "content-type": "application/json" },
    // ⚠ units too. The boom labels are formatted on the SERVER, so without
    // this a metric plot showed its boom heights in feet on screen while
    // the PDF said metres — screen and paper disagreeing about the same
    // number, which is the failure the shared layout exists to prevent.
    body: JSON.stringify({ positions: plot.positions, instruments: plot.instruments,
                           units: plot.units }),
  });
  if (!r.ok) throw new Error(`booms failed: ${r.status}`);
  const j = await r.json();
  return { booms: j.booms as BoomElevation[], space: j.space as number };
}

/** Where one position's NAME goes, fitted around the units and the other names.
 *
 * ⚠ The rule is labels.py — the same call the PDF makes — so the screen and the
 * paper choose the same slot. `x`/`y` are plot feet, `align` says which end of
 * the string is anchored, and `text` is the name as it should read (CAPS, trim
 * and (FOH) suffixes already applied) so the two drawings cannot disagree about
 * what a pipe is called.
 */
export interface PositionLabel {
  name: string; text: string;
  x: number; y: number; align: "left" | "right" | "center";
  overlap: number;
}

export async function positionLabels(
  plot: Plot, charW: number, textH: number,
  bounds?: [number, number, number, number],
): Promise<PositionLabel[]> {
  const r = await fetch("/api/labels", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({
      positions: plot.positions, instruments: plot.instruments,
      room_width: plot.room.width, char_w: charW, text_h: textH,
      // A position label carries its trim, so it is formatted too.
      units: plot.units,
      ...(bounds ? { bounds } : {}),
    }),
  });
  if (!r.ok) throw new Error(`labels failed: ${r.status}`);
  return (await r.json()).labels as PositionLabel[];
}

/** A plot on disk, as GET /plots lists it. */
export interface PlotFile { name: string; show: string; bytes: number; modified: number }

export async function listPlots(): Promise<
  { plots: PlotFile[]; folder: string; canPickFolder?: boolean }> {
  const r = await fetch("/api/plots");
  if (!r.ok) throw new Error(`could not list plots: ${r.status}`);
  return r.json();
}

/** Ask the SERVER to ask the person where plots should live.
 *
 *  🔴 SENDS NOTHING. A browser will not tell a page a real folder path — checked
 *  in the running app, `"path" in File.prototype` is false — so the page cannot
 *  pick the folder even if it wanted to. The server opens the operating system's
 *  own dialog instead, and the only string that reaches the filesystem is one
 *  the person chose there.
 *
 *  `changed` is false when the dialog was cancelled, which is not an error.
 */
export async function pickPlotsFolder(): Promise<
  { changed: boolean; folder: string }> {
  const r = await fetch("/api/plots/folder", { method: "POST" });
  if (!r.ok) throw new Error(await detailOf(r));
  return r.json();
}

export async function loadPlot(name: string): Promise<Plot> {
  const r = await fetch(`/api/plots/${encodeURIComponent(name)}`);
  if (!r.ok) throw new Error(await detailOf(r));
  return (await r.json()).plot as Plot;
}

/** Write a plot to disk, overwriting it.
 *
 * ⭐ Through the SERVER, not the browser. Save was built on the File System
 * Access API, which only Chrome and Edge have — everywhere else it fell back to
 * a download and every press left another copy: "Without Consent.plot (1).json"
 * (Jerry, 2026.09.24). This is a tool with its own local server, so the server
 * writes the file and Save means the same thing in every browser.
 */
export async function savePlot(name: string, plot: Plot): Promise<{ path: string }> {
  const r = await fetch("/api/save", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, plot }),
  });
  if (!r.ok) throw new Error(await detailOf(r));
  return r.json();
}

async function detailOf(r: Response): Promise<string> {
  const d = await r.json().then(j => j.detail).catch(() => r.statusText);
  return typeof d === "string" ? d : JSON.stringify(d);
}

/** What is in a PDF, before importing any of it. */
export interface PdfPage {
  page: number; width_in: number; height_in: number; items: number; images: number;
}

export async function pdfPages(file: File): Promise<{ pages: PdfPage[]; scales: string[] }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/import/pdf/pages", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await detailOf(r));
  return r.json();
}

/** A ground plan out of a PDF, in feet.
 *
 * ⚠ `scale` is not in the file and cannot be. A PDF measures PAPER — points, 72
 * to the printed inch — so the only route to feet is the drawing's own scale,
 * read off its title block by a person. Wrong by a factor of two and the result
 * is a perfectly plausible drawing of a different room.
 */
export async function pdfPaths(
  file: File, page: number, scale: string,
): Promise<DxfPaths & { note?: string }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("page", String(page));
  fd.append("scale", scale);
  const r = await fetch("/api/import/pdf", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await detailOf(r));
  return r.json();
}

/** Which build the server is. "dev" for anything not built from a tag.
 *
 * ⚠ Never falls back to a number. A working copy that reports itself as a
 * release sends whoever reads the report hunting in source that is not what
 * was running. */
export async function serverVersion(): Promise<string> {
  try {
    const r = await fetch("/api/health");
    if (!r.ok) return "unknown";
    return (await r.json()).version ?? "unknown";
  } catch {
    return "unknown";
  }
}


/** The DMX personalities, as the server holds them. ⭐ FETCHED, NEVER PORTED —
 *  the channel counts live in dmx.py so they cannot drift from the exporter. */
export interface DmxTable {
  family_models: Record<string, string[]>;
  /** Personalities that belong to no model — "Dimmer" — so they can be offered
   *  to a unit with no model to look up. */
  universal?: string[];
  profiles: Record<string, string[]>;
  /** Personalities the fixture has but whose channel count nobody published. */
  unpublished: Record<string, string[]>;
  suggested: Record<string, string>;
  sources: Record<string, string>;
}

export async function dmxTable(): Promise<DmxTable> {
  const r = await fetch("/api/dmx");
  if (!r.ok) throw new Error(`cannot load the DMX table: ${r.status}`);
  return r.json();
}
