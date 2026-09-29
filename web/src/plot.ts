/**
 * The .plot.json file format.
 *
 * Plain JSON, one file per show: readable in a text editor, diffable in git,
 * and openable in twenty years without a subscription. That is the whole point —
 * two shows in this designer's archive are locked inside .vwx files nothing on
 * the machine can read.
 *
 * Field names follow the Vectorworks/Lightwright exchange so paperwork.py can
 * import old shows with no translation layer.
 */

export interface Instrument {
  /** Unit number, unique within a position. */
  unit: number;
  channel?: number;
  /** The house circuit this unit is plugged into. §6.14.1 draws it in a HEXAGON.
   *
   *  ⚠ Never generated. Circuits depend on the house and have no set order
   *  (Jerry, 2026.09.23) — the only source is the venue's own circuit map. */
  circuit?: number | string;
  dimmer?: number | string;
  /** The START address. ⚠ A number for a plain address, a string for the
   *  universe form — "2/21" — which is why this is not just a number. */
  address?: number | string;
  /** The SPECIFIC fixture, e.g. "Source Four LED Series 2". ⚠ `type` is the
   *  photometric key and a Series 1 and a Series 2 share it — same optics.
   *  Their personalities are not the same, so the footprint depends on this. */
  model?: string;
  /** The DMX personality the fixture is set to, e.g. "HSI Plus 7". ⚠ NOT the
   *  same thing as `mode`, which is the photometric output mode. This one
   *  decides how many addresses the fixture occupies; that one decides how
   *  bright it is. */
  profile?: string;
  universe?: number;
  /** A key in the server's FIXTURES table, e.g. "S4 26". */
  type: string;
  /** Feet, plot coordinates. */
  x: number;
  y: number;
  /** Hang height in feet. Without it there is no throw and no level. */
  trim?: number;
  /** Height above the deck, for a unit on a BOOM. ⭐ On a vertical position
   *  every unit shares one x and y, so the height is the only thing that tells
   *  them apart — and the only thing to hang by. */
  height?: number;
  /** Where it points, in feet. focusH defaults to head height. */
  focusX?: number;
  focusY?: number;
  focusH?: number;
  /** "R52+R119" stacks; "R52/R119" is a split frame. */
  color?: string;
  gobo?: string;
  /** Tungsten lamp, e.g. "HPL 575". */
  lamp?: string;
  /** LED output mode, e.g. "Regulated 3200K". */
  mode?: string;
  /** Oval-beam units only (PARNel). Degrees the lens is turned — an oval beam
   *  whose angle nobody recorded is one somebody will hang wrong. */
  lensRotation?: number;
  wattage?: number;
  position?: string;
  purpose?: string;
  /** Barn doors, hats, gobos, irises. RP-2 puts GATE accessories (gobo, iris,
   *  rotator) inside the body and FRONT-of-lens ones (barn doors, hats) at the
   *  nose, so only the name is stored — the drawing works out where it goes.
   *  A list because a unit routinely carries two: a hat and a gobo. */
  accessories?: string[];
  notes?: string;
}

/** A hanging position: a pipe, a boom, a grid line. */
export interface Position {
  name: string;
  /** Endpoints in feet. A boom is drawn as a short line or a point. */
  x1: number; y1: number;
  x2: number; y2: number;
  /** Trim height in feet, if the whole position shares one. */
  trim?: number;
  /** Can this position's height actually change — a flown electric, a boom that
   *  gets re-set? RP-2 §2.1 asks for trim on the plan for MOVABLE positions
   *  only. A dead-hung grid pipe is not one, and a number that cannot change is
   *  clutter on every pipe in the room. The SECTION carries trim regardless. */
  movable?: boolean;
  /** What KIND of position, which decides how it is drawn.
   *
   *  An electric, pipe or grid is one heavy batten line. A catwalk is a
   *  WALKWAY — two architectural edges with a hanging pipe inboard of the
   *  downstage one — because a person stands on it and the units hang off the
   *  rail, not down the middle. A truss gets two chords and diagonals.
   *
   *  Vertical positions (boom, box boom, ladder) are NOT handled yet. */
  type?: "electric" | "pipe" | "grid" | "catwalk" | "truss"
        | "boom" | "box-boom" | "ladder" | "tormentor";
  /** How a FLOOR-STANDING vertical position meets the floor. Not decoration: a
   *  floor plate needs floor space and a sandbag, a flange is already in the
   *  building, and an electrician reading one as the other brings the wrong
   *  hardware.
   *
   *  ⚠ A ladder does not take one — it HANGS, so it carries a `trim` instead.
   *  A tormentor takes neither: it is bolted to the building. */
  mount?: "floor-plate" | "boom-base" | "flange";
  /** RP-2 §6.12 layout for this boom. The standard allows only ONE per plot. */
  layout?: "option1" | "option2";
  /** Front of house — over the audience, downstage of the plaster line, so its
   *  y is NEGATIVE. Catwalks are FOH by default (Jerry, 2026.09.23). The sheet
   *  has to be sized to reach the house or an FOH position is clipped off. */
  foh?: boolean;
  /** Real width in feet. Catwalks default to 3', trusses to 1'-6". */
  width?: number;
  /** How far inboard of the centre the hanging pipe sits. Varies by house —
   *  take it off the venue's section, not from a default. */
  railOffset?: number;
  /** Which end unit 1 sits at. Defaults to Jerry's habit: stage right on a
   *  lateral position, farthest downstage on one running upstage-downstage.
   *
   *  ⚠ Those defaults run in OPPOSITE directions here, because x increases
   *  toward stage right but y increases upstage — so stage right is the MAXIMUM
   *  x and downstage is the MINIMUM y. Do not "simplify" them into one rule. */
  numberFrom?: "SR" | "SL" | "DS" | "US" | "TOP" | "BOTTOM" | "PLASTER" | "CENTER";
  /** The circuits the HOUSE has on this position, in its own order. Bare
   *  numbers, or records with a location along the pipe. With locations, units
   *  can be matched to the nearest circuit; without them, matching refuses. */
  circuits?: Array<number | string | { id: number | string; x?: number; y?: number }>;
  /** Where the circuit list came from. A circuit list without a provenance is
   *  a rumour — this is what `/venue` asks for the rep plot to fill. */
  circuitSource?: string;
}

/** The room. Dimensions carry their source — a rental listing is not a survey. */
export interface Room {
  width: number;
  depth: number;
  /** Downstage edge of the stage, in feet from the room's downstage wall. It
   *  divides the ROOM into house and stage — everything downstage of it is
   *  front of house, and it is what makes an FOH position placeable INSIDE the
   *  room rather than beyond it. */
  plasterLine?: number;
  /** Floor to grid, in feet — the CEILING. Trims are checked against it. */
  gridHeight?: number;
  /** Where that figure came from. A grid height off a rental listing is not a
   *  measurement, and the difference decides whether a 14' trim is comfortable
   *  or impossible. */
  gridSource?: string;
  /** The ceiling over the AUDIENCE, for front-of-house positions. Usually higher
   *  than the stage grid — a catwalk at 18' in a room with a 15' grid is
   *  ordinary, and checking it against the grid reports a fault that is not
   *  there. */
  houseCeiling?: number;
  /** Where these numbers came from, and how old they are. */
  source?: string;
  /** Optional imported DXF, drawn underneath. Path is relative to the plot file. */
  basePlan?: string;
}

/** How the HOUSE gets power to a lamp — RP-2 §6.14.1, and it changes the plot's
 *  notation, not just its data.
 *
 *  "dimmer-per-circuit" is most houses (Jerry, 2026.09.23): the circuit is
 *  hard-wired to its own dimmer, so circuit and dimmer are ONE number and RP-2
 *  draws a single hexagon labelled "Circuit & Dimmer". Drawing two containers
 *  there is not harmlessly redundant — it tells the electrician there is a patch
 *  to make, and there is not.
 *
 *  ⭐ "dimmer-is-address" is the ETC reading (Jerry, 2026.09.29): a dimmer is a
 *  DMX shape, one address carrying intensity. The dimmer number stops being a
 *  separate fact, so the hexagon carries the address for a conventional unit
 *  exactly as it does for an LED, and a mixed plot reads the same throughout. */
export type ControlModel = "dimmer-per-circuit" | "hard-and-soft-patch"
  | "no-soft-patch" | "dimmer-is-address";

/** Line weights, in POINTS ON PAPER — the same on the sheet whatever the
 *  drawing scale. Everything is optional; what is left out keeps RP-2's value.
 *
 *  ⚠ Only widths. The dash patterns are not overridable: a chain-dash IS the
 *  centre line, and a plot that redefined it would be readable only by whoever
 *  drew it. */
export interface LineWeights {
  /** The three RP-2 weights. Setting `heavy` moves every heavy line at once. */
  light?: number;
  medium?: number;
  heavy?: number;
  /** One named RP-2 category — "batten", "architecture", "pool"… */
  styles?: Record<string, number>;
  /** One position type — "electric", "boom", "catwalk"… */
  positions?: Record<string, number>;
}

export interface Plot {
  /** The house's control model. Defaults to dimmer-per-circuit. */
  control?: ControlModel;
  /** Overrides for the drawn line widths. Absent means RP-2 throughout. */
  lineWeights?: LineWeights;
  /** What the plot READS in. Absent means imperial, so every plot drawn before
   *  this existed keeps reading the way it was drawn.
   *
   *  ⚠ Storage is FEET in both. This changes labels and what typed numbers
   *  mean, never a stored value. */
  units?: "imperial" | "metric";
  /** RP-2 §6.12: "choose only one type of layout per plot." */
  boomLayout?: "option1" | "option2";
  /** How instruments are ANGLED on the drawing. RP-2 p.2: "It is acceptable to
   *  visually orient the angle of each drawn luminaire to either focus points
   *  or 90° axes." Most plots use 90° mounts, so that is the default: a unit
   *  aiming at 320° is drawn at 0°.
   *
   *  🔴 Cosmetic ONLY. Every throw, pool and footcandle comes from the real
   *  focus — a unit DRAWN at 0° is a convention, a unit COMPUTED at 0° is a lie
   *  about where the light lands. test_agreement.py renders the same plot both
   *  ways and requires identical numbers. */
  symbolAngle?: "orthogonal" | "focus";
  /** Bump when the shape changes incompatibly. */
  formatVersion: 1;
  show: string;
  venue?: string;
  designer?: string;
  /** Whose drawing this is, for the title-block footer.
   *
   * ⚠ From the FILE, never from the code. The renderer used to print
   * "Twin Oaks Studios" and default the designer to "Design: Jerry Jonas", so a
   * plot drawn for any other venue or designer came out claiming his
   * authorship. Jerry, 2026.09.24: "I don't want to print anything that is
   * hardcoded about the venue because it will be used for other venues." */
  studio?: string;
  /** ISO date. */
  date?: string;
  revision?: string;
  room: Room;
  positions: Position[];
  instruments: Instrument[];
  /** Anything true about this plot that the fields cannot hold. */
  notes?: string[];
}

export function isPlot(x: unknown): x is Plot {
  const p = x as Plot;
  return !!p && p.formatVersion === 1 && !!p.room && Array.isArray(p.instruments);
}

/** The symbol cache key for one instrument: type, accessories, lamp.
 *
 * Two units of the same type with different accessories are different SHAPES,
 * so they cannot share a cache entry keyed on type alone. Built in one place
 * because main.ts asks the server for these keys and render.ts looks them up —
 * if the two ever spelled a key differently the symbol would silently fall back
 * to a plain ring and nobody would know why.
 *
 * ⭐ THE LAMP IS IN THE KEY because a retrofit changes the shape: a Source Four
 * with a 4WRD gains §6.16 source dots. Without it the first S4 asked for would
 * answer for every other S4 on the plot, retrofitted or not.
 *
 * ⚠ WHICH lamps change the symbol is the SERVER's business, not this file's.
 * The lamp is sent whenever there is one and the answer comes back identical
 * for a tungsten unit — a wasted cache slot, against keeping a second copy of
 * "a 4WRD is an LED" in the browser to go stale. That copy is exactly what put
 * the lamp dropdown a whole release behind LAMP_MF.
 */
export function symbolKey(inst: Instrument): string {
  const acc = (inst.accessories ?? []).map(a => a.trim()).filter(Boolean);
  const lamp = (inst.lamp ?? "").trim();
  if (!acc.length && !lamp) return inst.type;
  return `${inst.type}|${acc.join("+")}|${lamp}`;
}

/** Is this position a pipe that STANDS UP — a boom, box boom, ladder, torm?
 *
 * ⭐ In plan a vertical position is a POINT: every unit on it shares one x and y
 * and is told apart only by its height. Mirrors positions.is_vertical() in the
 * Python, including the part that measures rather than trusting the name — a
 * "box boom" is a point in some houses and a rail with real extent in others.
 */
export function isVertical(p: Position): boolean {
  const t = (p.type ?? "").trim().toLowerCase();
  const dx = Math.abs((p.x2 ?? p.x1) - p.x1);
  const dy = Math.abs((p.y2 ?? p.y1) - p.y1);
  if (["boom", "box-boom", "boom-box", "ladder", "tormentor", "torm"].includes(t))
    return !(dx > 0.5 || dy > 0.5);
  if (t) return false;
  return dx < 0.5 && dy < 0.5;
}

/** Front of house — DOWNSTAGE OF THE PLASTER LINE.
 *
 * ⚠ Corrected 2026.09.24. This used to mean "negative y", assuming `room` was
 * the stage and the house lay beyond it. The room is the WHOLE room: the test room
 * is 33' x 38' with its plaster line at y = 10, so the house is y 0–10 and the
 * stage 10–38, both inside one rectangle. An FOH position belongs inside it.
 */
export function isFoh(p: Position, plasterLine?: number): boolean {
  if (p.foh !== undefined) return p.foh;
  if (plasterLine === undefined) return false;
  return p.y1 < plasterLine;
}


/** The filename a plot saves to, from the show's name.
 *
 * ⚠ A show title is free text and a filename is not. "Without Consent: Act 2/3"
 * carries a slash, which on every platform either creates a directory that is
 * not there or is rejected outright — and a title of only punctuation would
 * come out as ".plot.json": hidden on macOS and Linux.
 */
export function plotFileName(show: string): string {
  const stem = (show ?? "")
    .replace(/[^\w -]+/g, " ")   // anything not a word char, space or hyphen
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
  return `${stem || "plot"}.plot.json`;
}

/** An empty plot, ready to be drawn on.
 *
 * ⭐ Jerry, 2026.09.24: "we need a new file feature." Until now the only way to
 * start was to open somebody else's plot and delete their rig out of it — which
 * is how a stranger's first plot ends up carrying a stray position, a leftover
 * gel and a designer's name in the title block.
 *
 * ⚠ The room has a SIZE, because it has to: the canvas fits itself to the room
 * and a plot with no dimensions has nothing to draw or scale against. 30' x 40'
 * is a starting point, not a measurement — `source` says exactly that, so the
 * figure cannot be mistaken for something anyone checked, and it prints that way
 * on the plot until it is replaced.
 *
 * ⚠ No designer and no studio. Those print in the title block, and a new plot
 * inheriting whoever used the tool last would put one person's name on another
 * person's drawing. They are typed in Show & Venue.
 */
export function newPlot(show = "Untitled"): Plot {
  return {
    formatVersion: 1,
    show,
    date: new Date().toISOString().slice(0, 10),
    revision: "A",
    control: "dimmer-per-circuit",
    room: {
      width: 30,
      depth: 40,
      source: "NOT MEASURED — a starting size. Set the room in Show & Venue.",
    },
    positions: [],
    instruments: [],
  };
}


/** The two ends of a position, from however many of the four the reader gave.
 *
 * ⭐ Jerry, 2026.09.24: "we need to be able to add grid pipes that are US to DS
 * — can't do that in the UI now — we could have x1 x2 y1 y2 and only require 3
 * values which would determine the direction."
 *
 * The form used to offer X1, Y1, X2 and write y2 = y1 behind the reader's back,
 * so every position it could make ran stage-left to stage-right. A pipe up and
 * down the deck could be drawn by hand-editing the JSON and no other way — and
 * the rest of the tool already understood one: positions.axis() calls it
 * `longitudinal` and numbers it from downstage, which is Jerry's own convention.
 *
 * ⭐ WHICH VALUE IS MISSING IS THE ANSWER. Leaving one blank says the position
 * does not move in that direction:
 *
 *   x2 blank   the run is UP AND DOWNSTAGE — x does not change
 *   y2 blank   the run is ACROSS — y does not change
 *   both blank a POINT, which is what a boom is in plan
 *   none blank a raked position, taken exactly as given
 *
 * ⚠ AND THE LENGTH SURVIVES THE TURN. Clearing X2 on a pipe that already runs
 * across would otherwise leave no extent in either direction — a 33-foot
 * electric would silently become a point. `previous` carries the run it had, so
 * blanking an axis TURNS the pipe rather than erasing it. Without this the
 * gesture the hint promises does the opposite of what it says.
 *
 * Returns null when x1 or y1 is missing, because there is no end to infer from.
 */
export interface Ends { x1: number; y1: number; x2: number; y2: number }

export function resolveEnds(
  x1?: number, y1?: number, x2?: number, y2?: number, previous?: Ends,
): Ends | null {
  if (x1 === undefined || y1 === undefined) return null;
  const ran = previous
    ? Math.hypot(previous.x2 - previous.x1, previous.y2 - previous.y1) : 0;

  if (x2 === undefined && y2 === undefined) return { x1, y1, x2: x1, y2: y1 };

  if (x2 === undefined) {
    // Runs up and downstage. Keep whatever y-run was typed; if there is none,
    // give it the length the pipe had before it was turned.
    const dy = (y2 as number) - y1;
    return { x1, y1, x2: x1, y2: dy !== 0 ? (y2 as number) : y1 + ran };
  }
  if (y2 === undefined) {
    const dx = x2 - x1;
    return { x1, y1, x2: dx !== 0 ? x2 : x1 + ran, y2: y1 };
  }
  return { x1, y1, x2, y2 };
}

/** How a position runs, for what to call it in the UI. Mirrors the naming in
 *  positions.py, which decides the numbering from the same fact. */
export function runOf(p: { x1: number; y1: number; x2: number; y2: number }):
    "across" | "up-and-downstage" | "raked" | "a point" {
  const dx = Math.abs(p.x2 - p.x1), dy = Math.abs(p.y2 - p.y1);
  if (dx < 0.01 && dy < 0.01) return "a point";
  if (dy < 0.01) return "across";
  if (dx < 0.01) return "up-and-downstage";
  return "raked";
}
