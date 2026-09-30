/**
 * Real feet in, screen pixels out. Get this right once.
 *
 * Two coordinate systems, and they disagree about which way is up:
 *
 *   PLOT    x → stage right, y → upstage (away from the audience), origin at
 *           the downstage-left corner of the room. Feet. This is what the JSON
 *           holds and what the Python thinks in.
 *   SCREEN  x → right, y → DOWN, origin top-left. Pixels. SVG and canvas both.
 *
 * So the y axis flips. Everything else is a scale and an offset.
 *
 * ⚠ Scale here is pixels per foot, NOT an architectural scale. Architectural
 * scale (¼" = 1'-0") belongs to paper and lives in scaled_pdf.py. On screen the
 * drawing zooms; on paper it must measure true. Do not confuse the two.
 */

export interface View {
  /** Pixels per foot. */
  scale: number;
  /** Plot coordinates (feet) of the point shown at the screen origin's column. */
  panX: number;
  panY: number;
  /** Size of the drawing surface, pixels. */
  width: number;
  height: number;
}

export interface Pt { x: number; y: number }

/** Plot feet → screen pixels. */
export function toScreen(p: Pt, v: View): Pt {
  return {
    x: (p.x - v.panX) * v.scale,
    y: v.height - (p.y - v.panY) * v.scale,
  };
}

/** Screen pixels → plot feet. The inverse; step 4 needs it for dragging. */
export function toPlot(p: Pt, v: View): Pt {
  return {
    x: p.x / v.scale + v.panX,
    y: (v.height - p.y) / v.scale + v.panY,
  };
}

/** Feet → pixels for a length (no offset, no flip). */
export function len(feet: number, v: View): number {
  return feet * v.scale;
}

/**
 * An SVG transform that lets the rest of the code draw in real feet.
 *
 * Wrap the drawing in <g transform={svgTransform(view)}> and then emit
 * coordinates in feet directly — the group handles the scale and the y flip.
 * The SVG source then reads in the units of the room, which is worth having
 * when something looks wrong.
 *
 * ⚠ It flips text too. Use counterFlip() on any <text>.
 */
export function svgTransform(v: View): string {
  return `translate(${-v.panX * v.scale} ${v.height + v.panY * v.scale}) scale(${v.scale} ${-v.scale})`;
}

/** Undo the y flip for a text element sitting at (x, y) in plot feet. */
export function counterFlip(x: number, y: number): string {
  return `translate(${x} ${y}) scale(1 -1)`;
}

/** Fit a room of w × h feet into the surface, with a margin in feet. */
export function fitView(
  roomW: number, roomH: number, width: number, height: number, marginFt = 3,
  houseFt = 0, leftFt = 0,
): View {
  // ⭐ `houseFt` is how far DOWNSTAGE the plot reaches past the room — front of
  // house positions sit over the audience at negative y. Fit to the room alone
  // and a catwalk is simply not on screen, which is the same failure the PDF had
  // before foh_extent(); there the clipping guard caught it, and here nothing
  // would: the drawing just quietly lacks a position.
  // ⭐ `leftFt` is the same problem in the other axis: RP-2 §6.12 boom
  // elevations sit off the stage-left edge at NEGATIVE x. The PDF counts this
  // space before setting its origin; the browser fitted to the room alone, so
  // an elevation drawn there would simply be off the left of the canvas.
  const totalH = roomH + houseFt;
  const totalW = roomW + leftFt;
  const scale = Math.min(width / (totalW + marginFt * 2), height / (totalH + marginFt * 2));
  // center what is actually drawn, not just the room
  const slackX = (width / scale - totalW) / 2;
  const slackY = (height / scale - totalH) / 2;
  // ⚠ MINUS houseFt. toScreen() is y_screen = height − (y_plot − panY)·scale, so
  // a point is on the canvas only while y_plot ≥ panY. The house sits at
  // NEGATIVE y, so panY has to move further negative to reach it. Adding it
  // opened the space upstage instead — empty paper at the back of the room and
  // the catwalk still off the bottom.
  // ⚠ MINUS leftFt, for the same reason as houseFt: a point is on the canvas
  // only while x_plot ≥ panX, and the elevations sit below zero.
  return { scale, panX: -slackX - leftFt, panY: -slackY - houseFt, width, height };
}

/** DEPRECATED — always 0. Kept so callers do not break.
 *
 * It existed to extend the canvas downstage for front-of-house positions drawn
 * at negative y. That was a wrong model: the room is the whole room, house and
 * stage, and an FOH position belongs inside it (Jerry, 2026.09.24). Nothing
 * needs extra canvas any more.
 */
export function fohExtent(
  _positions: { y1: number; y2?: number; width?: number; type?: string; foh?: boolean }[],
): number {
  return 0;
}

/** Feet as feet-and-inches: 13.75 → 13'-9" */
export const M_PER_FOOT = 0.3048;
export type UnitSystem = "imperial" | "metric";

/** ⚠ AMBIENT, and deliberately so. The editor holds exactly ONE plot, every
 *  render is driven from it, and `draw()` sets this before anything is
 *  formatted — so threading a system argument through every render function
 *  would be ceremony around a value that cannot differ between two of them.
 *
 *  ⚠ FEET REMAIN THE INTERNAL UNIT. Nothing stored, measured or computed
 *  changes; this decides only how a number is WRITTEN. The moment a conversion
 *  happens anywhere but at the point of display, there are two sets of
 *  arithmetic to keep in step and the wrong one is the one nobody watches. */
let _system: UnitSystem = "imperial";

export function setUnitSystem(u: string | undefined): void {
  _system = String(u ?? "").toLowerCase().startsWith("met") ? "metric" : "imperial";
}

export function unitSystem(): UnitSystem { return _system; }

/** A length, as the plot's reader writes it. ALWAYS takes feet. */
export function fmtFt(feet: number | null | undefined,
                      system: UnitSystem = _system): string {
  if (feet === null || feet === undefined || !isFinite(feet)) return "—";
  if (system === "metric") return `${(feet * M_PER_FOOT).toFixed(2)} m`;
  const neg = feet < 0;
  const a = Math.abs(feet);
  let whole = Math.floor(a);
  let inches = Math.round((a - whole) * 12);
  if (inches === 12) { whole += 1; inches = 0; }
  return `${neg ? "-" : ""}${whole}'-${inches}"`;
}

/** An illuminance. ALWAYS takes footcandles.
 *
 *  🔴 The label travels with the number. A lux figure written "179 fc" is a
 *  false statement that looks authoritative. */
export function fmtFc(fc: number | null | undefined,
                      system: UnitSystem = _system): string {
  if (fc === null || fc === undefined || !isFinite(fc)) return "—";
  return system === "metric"
    ? `${Math.round(fc / (M_PER_FOOT * M_PER_FOOT))} lx`
    : `${Math.round(fc)} fc`;
}

/** Where a piece of notation sits relative to an instrument, in FEET.
 *
 * ⭐ Front and back belong to the INSTRUMENT, not to the page. `d` is measured
 * along the unit's own axis: positive is BEHIND the light (where RP-2 §6.14.2
 * puts circuit, dimmer and channel), negative is in FRONT, beyond the lens
 * (colour and focus).
 *
 * ⚠ This lived twice — as fixed page offsets in render.ts and as `_along` in
 * symbols.py — and the two drifted: the screen put the channel 1.5 ft down the
 * PAGE whatever way the unit aimed, so a unit focused downstage had its channel
 * number sitting in its own beam and its colour behind it. One formula, tested
 * on both sides, is what stops that.
 *
 * @param drawnDeg the angle the SYMBOL is drawn at — after any orthogonal
 *   snap. Not the true pan, or the label follows a rotation the reader cannot
 *   see.
 */
export function notationAnchor(x: number, y: number, drawnDeg: number, d: number): Pt {
  const r = (drawnDeg * Math.PI) / 180;
  return { x: x - d * Math.sin(r), y: y + d * Math.cos(r) };
}

/** The farthest any part of a symbol reaches from its yoke, in FEET.
 *
 * The mirror of symbols.py's `radius()`. Notation has to clear the symbol, and
 * symbols are not one size — an ERS is 1'-8" long, a striplight is six feet,
 * and an accessory on the nose adds more. A fixed offset put the channel circle
 * on top of every ellipsoidal on the paper; the screen had the same constant.
 *
 * ⚠ Match each kind explicitly. A fall-through default is what made the Python
 * version unpack a point LIST as one pair when the "fill" primitive arrived.
 */
export function symbolRadius(prims: readonly unknown[] | undefined): number {
  let best = 0;
  for (const raw of prims ?? []) {
    const p = raw as { k: string; pts?: [number, number][]; a?: [number, number];
                       b?: [number, number]; c?: [number, number]; r?: number };
    let pts: [number, number][] = [];
    let pad = 0;
    if (p.k === "poly" || p.k === "fill") pts = p.pts ?? [];
    else if (p.k === "line") pts = [p.a, p.b].filter(Boolean) as [number, number][];
    else if (p.k === "circle") { pts = p.c ? [p.c] : []; pad = p.r ?? 0; }
    else if (p.k === "text") pts = p.c ? [p.c] : [];
    else continue;
    for (const [a, c] of pts) best = Math.max(best, Math.hypot(a, c) + pad);
  }
  return best;
}

/** The transform that places and aims an instrument symbol.
 *
 * 🔴 Jerry, 2026.09.24: "the instruments on the US DS electric are pointing the
 * wrong way when they are focused."
 *
 * render.ts wrote `rotate(-pan)`. SVG's rotate(θ) sends (x, y) to
 * (x·cosθ − y·sinθ, x·sinθ + y·cosθ), and a symbol's nose sits at local
 * (a, c) = (−1, 0), plotted at (c, a) = (0, −1). Negating the angle therefore
 * agrees with symbols.draw() at 0° and 180° — where sin is zero — and MIRRORS
 * it at ±90°:
 *
 *      pan    paper      screen, with -pan
 *        0   (0, −1)     (0, −1)   same
 *       90   (+1, 0)     (−1, 0)   OPPOSITE
 *      180   (0, +1)     (0, +1)   same
 *      270   (−1, 0)     (+1, 0)   OPPOSITE
 *
 * ⚠ It survived because nothing drawn in plan had ever aimed sideways. Every
 * unit in the sample aims up or downstage, and boom units — which do aim across
 * — stopped being drawn in plan when they moved to the §6.12 elevations. The
 * first pipe running up and downstage put five units at pan ±90 and the error
 * appeared at once.
 */
export function symbolTransform(x: number, y: number, drawnDeg: number): string {
  return `translate(${x} ${y}) rotate(${drawnDeg})`;
}

/** Where the LENS points, for a symbol placed by symbolTransform.
 *
 * This applies SVG's own rotation matrix to the nose, so it is a statement
 * about what the browser will draw — not a restatement of the angle we chose.
 * It has to agree with symbols.draw(): 0° aims downstage, 90° stage right.
 */
export function lensDirection(drawnDeg: number): Pt {
  const r = (drawnDeg * Math.PI) / 180;
  const cos = Math.cos(r), sin = Math.sin(r);
  const nx = 0, ny = -1;                       // the nose in the symbol's own frame
  return { x: nx * cos - ny * sin, y: nx * sin + ny * cos };
}

/** Where an imported base plan sits once the designer has placed it.
 *
 *  ⚠ THE ONLY COPY OF THIS ARITHMETIC. What it returns is both what gets drawn
 *  and what gets sent to the exporter, so the screen and the paper cannot
 *  disagree about where the venue's drawing is. The temptation is to send the
 *  import plus the transform and let the server apply it — that is the same sum
 *  in two languages, and `server/test_agreement.py` is the record of the last
 *  time that made the screen and the print differ.
 *
 *  The turn is about the STAGE ORIGIN, not the drawing's own centre, which
 *  matches `dxf_bridge`'s `rotate_deg` and means a 90° turn also swings the
 *  plan sideways. That is arithmetically honest and visually surprising, so the
 *  x and y boxes are there to put it back.
 */
export function placeBase<T extends { points: [number, number][] }>(
  paths: readonly T[], xf: { x: number; y: number; rotate: number },
): T[] {
  const { x, y, rotate } = xf;
  // Nothing to do is worth short-circuiting: a base plan can be thousands of
  // points and this runs on every redraw.
  if (!x && !y && !rotate) return paths as T[];
  const a = rotate * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
  return paths.map(p => ({
    ...p,
    points: p.points.map(([px, py]) =>
      [px * ca - py * sa + x, px * sa + py * ca + y] as [number, number]),
  }));
}
