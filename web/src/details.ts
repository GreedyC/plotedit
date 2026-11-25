/**
 * Show & Venue — the fields that identify a plot, and the room it is drawn in.
 *
 * ⭐ Jerry, 2026.09.24: "do we need a section on the UI to enter the venue and
 * show information." Yes, and the answer got sharper the same day: the renderer
 * stopped hardcoding "Twin Oaks Studios" and "Design: Jerry Jonas", so the
 * title block now prints whatever the FILE says. Before this panel the only way
 * to put a name on a drawing — or to keep the wrong one off it — was to open
 * the .plot.json in a text editor.
 *
 * ⚠ Two kinds of field, and the difference matters:
 *
 *   IDENTITY   show, venue, designer, director, scenic design, studio,
 *              revision. These print, and
 *              nothing else changes. A redraw is enough.
 *   THE ROOM   width, depth, grid height, house ceiling, plaster line. Every
 *              one of these moves the drawing or changes what is CHECKED — the
 *              grid height is what trims are judged against, the plaster line
 *              decides which positions are front of house. These have to
 *              recompute, not just redraw.
 */
import type { Store } from "./store.js";
import type { ControlModel } from "./plot.js";
import { parseFeet } from "./feet.js";
import { fmtFt } from "./geometry.js";

export interface DetailDeps {
  /** Something that only prints has changed — redraw. */
  onChange: () => void;
  /** The ROOM has changed — the numbers are stale until the server answers. */
  onGeometry: () => void;
  /** How symbols are DRAWN has changed — the outlines held are stale. */
  onSymbols: () => void;
}

const UNITS = [
  { value: "imperial", label: "Imperial — feet and inches" },
  { value: "metric", label: "Metric — metres" },
];

// ⭐ 2025 USITT RP, Figure 3.1.4.0.4: write the beam angle in the barrel
// instead of the mark. One setting for the whole plot (Jerry, 2026.10.09).
const BEAM_ANGLE = [
  { value: "mark", label: "A mark in the lens (RP)" },
  { value: "number", label: "The number in the barrel" },
];

const CONTROL: { value: ControlModel; label: string }[] = [
  { value: "dimmer-per-circuit", label: "Dimmer per circuit (most houses)" },
  { value: "hard-and-soft-patch", label: "Hard and soft patch" },
  { value: "no-soft-patch", label: "No soft patch" },
  // ⭐ Jerry, 2026.09.29: a dimmer is one DMX address carrying intensity, so
  // the dimmer number and the address are the same fact.
  { value: "dimmer-is-address", label: "Dimmer = address (ETC)" },
];

function field(
  label: string, value: string | number | undefined,
  apply: (raw: string) => void,
  opts: { step?: number; hint?: string; wide?: boolean;
          options?: { value: string; label: string }[] } = {},
): HTMLElement {
  const wrap = document.createElement("label");
  wrap.className = "card-field" + (opts.wide ? " wide" : "");
  const cap = document.createElement("span");
  cap.textContent = label;
  if (opts.hint) { cap.title = opts.hint; wrap.title = opts.hint; }
  wrap.appendChild(cap);

  let input: HTMLInputElement | HTMLSelectElement;
  if (opts.options) {
    input = document.createElement("select");
    for (const o of opts.options) {
      const el = document.createElement("option");
      el.value = o.value; el.textContent = o.label;
      input.appendChild(el);
    }
    input.value = String(value ?? "");
  } else {
    // ⚠ A length is a TEXT box. type="number" silently discards 1'6".
    input = document.createElement("input");
    input.type = opts.step ? "text" : "text";
    if (opts.step) input.inputMode = "decimal";
    input.value = opts.step && typeof value === "number" ? fmtFt(value)
      : value === undefined || value === null ? "" : String(value);
  }
  // change, not input — a half-typed room width never reaches the server.
  input.addEventListener("change", () => apply(input.value.trim()));
  wrap.appendChild(input);
  return wrap;
}

/** A number field that leaves the value ALONE when the box is emptied to
 *  undefined, rather than reading "" as 0. A grid height of 0 is a claim that
 *  the ceiling is on the floor; a grid height of undefined is "not known yet",
 *  and the checks already say so out loud. */
export function feet(raw: string): number | undefined {
  const v = parseFeet(raw);
  // ⚠ null means nonsense; treated as "leave it alone", and the caller says so.
  return v === null ? undefined : v;
}

export function renderDetails(host: HTMLElement, store: Store, deps: DetailDeps): void {
  host.replaceChildren();
  const p = store.plot;

  const group = (title: string, fields: HTMLElement[]) => {
    const box = document.createElement("div");
    box.className = "card";
    const h = document.createElement("p");
    h.className = "group-label";
    h.textContent = title;
    box.appendChild(h);
    for (const f of fields) box.appendChild(f);
    host.appendChild(box);
  };

  group("The drawing", [
    field("Units", p.units ?? "imperial",
          v => { store.setMeta({ units: v as "imperial" | "metric" }); deps.onGeometry(); },
          { wide: true, options: UNITS,
            hint: "What the plot READS in. Everything is stored in feet either way, "
                + "so switching re-labels the drawing rather than changing it — no "
                + "number moves. Typed values follow: on a metric plot a bare number "
                + "is metres, and 5'6\" is still 5'6\"." }),
    field("Show", p.show, v => { store.setMeta({ show: v }); deps.onChange(); }, { wide: true }),
    field("Venue", p.venue, v => { store.setMeta({ venue: v }); deps.onChange(); }, { wide: true }),
    field("Designer", p.designer, v => { store.setMeta({ designer: v }); deps.onChange(); },
          { hint: "Printed in the title block. Left blank, nothing is printed — "
                + "the drawing never claims an author the file does not name." }),
    field("Studio", p.studio, v => { store.setMeta({ studio: v }); deps.onChange(); },
          { hint: "Printed along the bottom of the title block." }),
    field("Director", p.director, v => { store.setMeta({ director: v }); deps.onChange(); },
          { hint: "Printed in the title block under the lighting credit. Left blank, "
                + "no line is printed at all." }),
    field("Scenic design", p.scenicDesigner,
          v => { store.setMeta({ scenicDesigner: v }); deps.onChange(); },
          { hint: "Printed in the title block under the director. Left blank, "
                + "no line is printed at all." }),
    field("Revision", p.revision, v => { store.setMeta({ revision: v }); deps.onChange(); },
          { wide: true,
            hint: "The designator, then what changed — \"H — pipes retrimmed\". The "
                + "first word prints beside Rev in the title block; the rest prints "
                + "under the sheet name. One word on its own is fine." }),
    field("Date", p.date, v => { store.setMeta({ date: v }); deps.onChange(); },
          { hint: "The date on the plot, printed in the title block. Blank prints the day it is exported." }),
  ]);

  // ⚠ The unit in the CAPTION has to follow the plot, or a metric plot shows
  // "Width (ft)" above a box reading 10.06 m — a number and a label
  // contradicting each other, which is the one failure this whole pass existed
  // to prevent. Caught by Jerry in the browser, 2026.09.25, after the drawing
  // and the paperwork were already right.
  const U = (p.units ?? "imperial") === "metric" ? "m" : "ft";

  group("The room", [
    field(`Width (${U})`, p.room.width,
          v => { const n = feet(v); if (n !== undefined) { store.setRoom({ width: n }); deps.onGeometry(); } },
          { step: 0.5 }),
    field(`Depth (${U})`, p.room.depth,
          v => { const n = feet(v); if (n !== undefined) { store.setRoom({ depth: n }); deps.onGeometry(); } },
          { step: 0.5 }),
    field(`Grid (${U})`, p.room.gridHeight,
          v => { store.setRoom({ gridHeight: feet(v) }); deps.onGeometry(); },
          { step: 0.5, hint: "Floor to grid. Trims are checked against it. Blank means "
                           + "NOT KNOWN, and the checks say so rather than passing quietly." }),
    field(`House ceiling (${U})`, p.room.houseCeiling,
          v => { store.setRoom({ houseCeiling: feet(v) }); deps.onGeometry(); },
          { step: 0.5, hint: "The ceiling over the AUDIENCE. A catwalk at 18' in a room "
                           + "with a 15' grid is ordinary — checking it against the grid "
                           + "reports a fault that is not there." }),
    field(`Plaster line (${U})`, p.room.plasterLine,
          v => { store.setRoom({ plasterLine: feet(v) }); deps.onGeometry(); },
          { step: 0.5, hint: "Divides the room into house and stage; it is what makes a "
                           + "position front of house. A black box has none — leave it blank." }),
    field("Control", p.control ?? "dimmer-per-circuit",
          v => { store.setMeta({ control: v as ControlModel }); deps.onChange(); },
          { wide: true, options: CONTROL,
            hint: "RP-2 6.14.1. This changes the NOTATION drawn, not just the data: "
                + "with dimmer per circuit the circuit and dimmer are one number and "
                + "one hexagon, because there is no patch to make." }),
    field("Beam angle", p.angleInBarrel ? "number" : "mark",
          v => { store.setMeta({ angleInBarrel: v === "number" || undefined });
                 deps.onSymbols(); },
          { wide: true, options: BEAM_ANGLE,
            hint: "How an ellipsoidal shows its beam angle, on every unit in the plot. "
                + "The 2025 USITT RP allows either. The number is plainer where many "
                + "units share one body, and a 40° and a 10° both carry no mark." }),
  ]);

  // ⭐ Jerry, 2026.09.25, relaying a tester: "the lines are too thick for pipes."
  // RP-2 fixes three weights and the module picked the points for them — heavy
  // was 1.7pt, correct by the standard and heavy on the page. These are POINTS
  // ON PAPER, so a value means the same at every drawing scale.
  //
  // ⚠ The three named weights come first deliberately. Moving `heavy` fixes the
  // complaint everywhere at once and keeps RP-2's grouping intact — heavy is
  // what physically exists, light is notation about it. The per-type boxes
  // below break that grouping, which is sometimes what you want and is never
  // the place to start.
  const w = p.lineWeights ?? {};
  const pts = (label: string, value: number | undefined,
               path: Parameters<typeof store.setWeight>[0], hint: string) =>
    field(label, value, raw => {
      const t = raw.trim();
      if (t === "") { store.setWeight(path, undefined); deps.onChange(); return; }
      const n = Number(t);
      // ⚠ Nonsense leaves the value alone rather than storing NaN, and a zero
      // is refused: a zero-width line is not thin, it is absent.
      if (Number.isFinite(n) && n > 0) { store.setWeight(path, n); deps.onChange(); }
    }, { step: 0.1, hint });

  group("Line weights (points on paper)", [
    pts("Light", w.light, "light",
        "RP-2's lightest weight — notation, leaders, dimensions, beam pools. Default 0.5."),
    pts("Medium", w.medium, "medium",
        "Positions — pipes, booms, catwalks — plus the building (drawn gray), soft goods "
      + "and the centre and plaster lines. Default 0.9. Lower this if the pipes read heavy."),
    pts("Heavy", w.heavy, "heavy",
        "The instruments, and the sheet border and title block. Default 1.7. "
      + "The 2025 USITT RP makes the units the heaviest thing on the plot."),
    pts("Electrics", w.positions?.electric, "positions.electric",
        "Overrides the weight for electrics, pipes and grids only. Leave blank "
      + "to follow Medium."),
    pts("Booms", w.positions?.boom, "positions.boom",
        "Booms, box booms and ladders. Leave blank to follow Medium."),
    pts("Catwalks", w.positions?.catwalk, "positions.catwalk",
        "A catwalk is drawn as architecture, not as a pipe — this is its edges. "
      + "Leave blank to follow Medium."),
  ]);

  group("Where the figures came from", [
    field("Room source", p.room.source,
          v => { store.setRoom({ source: v || undefined }); deps.onChange(); },
          { wide: true,
            hint: "Printed across the top of the plot. A dimension off a rental listing "
                + "is not a measurement, and this is where the drawing says which it is." }),
    field("Grid source", p.room.gridSource,
          v => { store.setRoom({ gridSource: v || undefined }); deps.onChange(); },
          { wide: true }),
  ]);
}
