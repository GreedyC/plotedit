/**
 * The positions panel — edit the pipes, not just what hangs on them.
 *
 * ⭐ Until now a position could only be created or changed by hand-editing the
 * .plot.json. That made booms, catwalks and trims effectively unreachable from
 * the editor, which is backwards: the trim is the number a designer changes most
 * often at tech, and the position type decides how the whole plot draws.
 *
 * Not selection-based. A plot has a handful of positions and they are all worth
 * seeing at once — unlike instruments, where a list of sixty would be a wall.
 */
import type { Plot, Position } from "./plot.js";
import { isVertical, resolveEnds, runOf, lengthOf, angleOf,
         endsFromLengthAngle, duplicateNames, duplicateUnits,
         nextPositionName } from "./plot.js";
import type { Store } from "./store.js";
import { renumber } from "./api.js";
import { confirmDelete, confirmSharedName, sharedNameRenumberNote } from "./confirm.js";
import { parseFeet } from "./feet.js";
import { fmtFt } from "./geometry.js";

/** Two decimals, for a box a human types into. A pipe at 11.999999 degrees is
 *  at twelve degrees, and showing the noise invites someone to retype it. */
const round2 = (n: number) => Math.round(n * 100) / 100;

const TYPES = ["electric", "pipe", "grid", "catwalk", "truss",
               "boom", "box-boom", "ladder", "tormentor"] as const;
const MOUNTS = ["", "boom-base", "floor-plate", "flange"] as const;

export interface PositionDeps {
  onChange: () => void;
  /** Start numbering this run by clicking the units in order. Optional so a
   *  caller without a plan to click on still compiles — see `onDrawPipe`. */
  onNumberSeq?: (pos: Position, start: number) => void;
  /** Say something the user needs to read — a refusal, or a nudge to renumber.
   *  Optional so a caller that does not have a status line still compiles. */
  onStatus?: (msg: string, bad?: boolean) => void;
}

/** Where the next unit on a BOOM goes, in feet above the deck.
 *
 * 🔴 Jerry, 2026.09.24: "adding an instrument to a boom doesn't seem to work."
 * It added one with `height: p.trim`, and a boom position record carries no
 * trim — so the height was undefined, which puts a unit in the elevation's
 * NO HEIGHT RECORDED list and skips it in plan. The unit was in the file and on
 * neither drawing.
 *
 * ⭐ BELOW the lowest, stepping by the spacing already in use. On a boom the
 * numbers run top down — 1 at 12'-0", 2 at 8'-0", 3 at 4'-6" in the sample — so
 * going downwards keeps max(unit)+1 the right number and needs no renumber.
 *
 * ⚠ Returns undefined when there is nowhere left. Stacking two units at one
 * height is worse than refusing: on a boom they are a single point in plan and
 * a single mark on the elevation, so the drawing would show one and the
 * paperwork two.
 */
export const MIN_BOOM_GAP = 1;

export function nextBoomHeight(
  existing: (number | undefined)[], positionTrim?: number,
): number | undefined {
  const heights = existing.filter((h): h is number => h !== undefined)
    .sort((a, b) => b - a);
  if (!heights.length) return positionTrim ?? 12;      // a first unit goes high side

  const snap = (v: number) => Math.round(v * 2) / 2;   // to the nearest half foot
  const gaps = heights.slice(1).map((h, k) => heights[k]! - h);
  const step = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 4;

  const lowest = heights[heights.length - 1]!;
  const below = snap(lowest - step);
  if (below >= MIN_BOOM_GAP) return below;

  // No room underneath. Fall back to the widest gap BETWEEN units — the same
  // rule a pipe uses. The new unit is numbered last and so sits out of order on
  // the boom; the caller states that, and leaves the fix to the designer.
  let best: number | undefined;
  let widest = MIN_BOOM_GAP;
  for (let k = 0; k < heights.length - 1; k++) {
    const gap = heights[k]! - heights[k + 1]!;
    if (gap > widest) { widest = gap; best = snap(heights[k + 1]! + gap / 2); }
  }
  if (best !== undefined && !heights.includes(best)) return best;

  // Last resort: halfway between the lowest unit and the deck, if that is a
  // real gap. Otherwise the boom is full and the caller must say so.
  const half = snap(lowest / 2);
  if (lowest >= MIN_BOOM_GAP * 2 && half >= MIN_BOOM_GAP && !heights.includes(half)) return half;
  return undefined;
}

function field(
  label: string, value: string | number | undefined,
  apply: (raw: string) => void,
  opts?: { options?: readonly string[]; step?: number; hint?: string; feet?: boolean },
): HTMLElement {
  const wrap = document.createElement("label");
  wrap.className = "pos-field";
  const cap = document.createElement("span");
  cap.textContent = label;
  if (opts?.hint) cap.title = opts.hint;
  wrap.appendChild(cap);

  let input: HTMLInputElement | HTMLSelectElement;
  if (opts?.options) {
    input = document.createElement("select");
    for (const o of opts.options) {
      const el = document.createElement("option");
      el.value = o; el.textContent = o || "—";
      input.appendChild(el);
    }
    input.value = String(value ?? "");
  } else {
    // ⚠ A length is a TEXT box: type="number" silently discards 1'6". See
    // feet.ts — that is how a focus height typed as 1'-6" ended up unset.
    input = document.createElement("input");
    input.type = opts?.feet ? "text" : opts?.step ? "number" : "text";
    if (opts?.feet) input.inputMode = "decimal";
    if (opts?.step && input.type === "number") input.step = String(opts.step);
    input.value = opts?.feet && typeof value === "number" ? fmtFt(value)
      : value === undefined || value === null ? "" : String(value);
  }
  // change, not input — a half-typed trim never reaches the server
  input.addEventListener("change", () => apply(input.value.trim()));
  wrap.appendChild(input);
  return wrap;
}

export function renderPositions(
  host: HTMLElement, store: Store, deps: PositionDeps,
): void {
  host.replaceChildren();
  const plot: Plot = store.plot;

  // forEach, not an index loop: `noUncheckedIndexedAccess` is on, so
  // positions[i] is Position | undefined and every read needs a guard. The
  // callback hands back a Position that is known to exist.
  // ⭐ ONCE for the whole panel, not once per row. Every row asks whether its
  // name clashes, and rebuilding the set eleven times to answer eleven
  // questions is the kind of thing that makes a panel feel slow on a big plot.
  const clashes = duplicateNames(plot.positions);

  plot.positions.forEach((p) => {
    const box = document.createElement("div");
    box.className = "pos-row";

    const set = (patch: Partial<Position>) => {
      store.begin(null);
      Object.assign(p, patch);
      store.commit();
      deps.onChange();
    };
    // ⚠ Feet and inches, and NONSENSE IS REFUSED rather than written. The old
    // version was `Number(raw)`, which turns "6ft" into NaN and stores it —
    // a position whose x1 is NaN draws nowhere and reports nothing.
    const num = (raw: string): number | undefined | null => {
      const v = parseFeet(raw);
      if (v === null) {
        deps.onStatus?.(`"${raw}" is not a length — try 1'6", 18" or 1.5`, true);
        return null;
      }
      return v;
    };

    // ⭐ RENAMING A PIPE TAKES ITS RIG WITH IT, for the same reason changing its
    // trim does — a unit says which position it is on by NAME, so a rename that
    // leaves the units behind orphans every light on the pipe. They keep
    // pointing at a name no position has any more, and drop out of the
    // schedule, the hookup and the focus chart without a word.
    //
    // 🔴 FOUND BY THE WARNING BELOW TELLING PEOPLE TO DO IT. The duplicate-name
    // note says "Rename one" — which, before this, was advice that broke the
    // plot it was trying to fix.
    box.appendChild(field("Name", p.name, v => {
      const from = p.name.trim().toLowerCase();
      const to = v.trim();
      if (!to || to.toLowerCase() === from) { set({ name: v }); return; }
      store.begin(null);
      p.name = v;
      let moved = 0;
      for (const inst of plot.instruments) {
        if ((inst.position ?? "").trim().toLowerCase() !== from) continue;
        inst.position = to;
        moved++;
      }
      store.commit();
      deps.onChange();
      if (moved) deps.onStatus?.(`${to} — ${moved} unit${moved === 1 ? "" : "s"} came with it.`);
    }, { hint: "Every unit on this position is renamed with it" }));
    box.appendChild(field("Type", p.type ?? "electric",
      v => set({ type: v as Position["type"] }), { options: TYPES }));
    // ⭐ Moving a pipe MOVES ITS RIG. Setting the trim alone changed only the
    // label while every unit went on computing from the old height — the plot
    // would state one trim and compute another. Units keep any deliberate
    // offset, so a drop-arm stays a drop-arm.
    box.appendChild(field("Trim", p.trim, v => {
      const t = num(v);
      if (t === null) return;
      const old = p.trim;
      store.begin(null);
      p.trim = t;
      if (t !== undefined && old !== undefined) {
        for (const inst of plot.instruments) {
          if ((inst.position ?? "").trim().toLowerCase() !== p.name.trim().toLowerCase()) continue;
          if (inst.trim === undefined) continue;
          inst.trim = inst.trim + (t - old);
        }
      }
      store.commit();
      deps.onChange();
    }, { feet: true, hint: "Moves every unit on this position with it, keeping any deliberate offset" }));

    if (isVertical(p)) {
      // ⚠ A ladder HANGS and a tormentor is bolted to the building — neither
      // takes a floor mount. Offering one invites hardware that does not exist.
      const t = (p.type ?? "").toLowerCase();
      if (t !== "ladder" && t !== "tormentor" && t !== "torm") {
        box.appendChild(field("Mount", p.mount ?? "",
          v => set({ mount: (v || undefined) as Position["mount"] }),
          { options: MOUNTS, hint: "A floor plate needs floor space and a sandbag; a flange is already in the building" }));
      }
      box.appendChild(field("X", p.x1, v => { const n = num(v);
        if (n === null || n === undefined) return; set({ x1: n, x2: n }); }, { feet: true }));
      box.appendChild(field("Y", p.y1, v => { const n = num(v);
        if (n === null || n === undefined) return; set({ y1: n, y2: n }); }, { feet: true }));
    } else {
      // ⭐ FOUR ENDS, THREE REQUIRED. Leaving one blank says the position does
      // not move in that direction — blank X2 runs it up and downstage, blank
      // Y2 runs it across. The old form offered X1/Y1/X2 and wrote y2 = y1
      // behind the reader's back, so every position it could make ran
      // stage-left to stage-right, and a pipe up the deck needed a text editor.
      const end = (label: string, cur: number, key: "x1" | "y1" | "x2" | "y2") =>
        field(label, cur, v => {
          const n = num(v);
          if (n === null) return;                  // nonsense; num() already said so
          const next = { x1: p.x1, y1: p.y1, x2: p.x2, y2: p.y2, [key]: n };
          const ends = resolveEnds(next.x1, next.y1, next.x2, next.y2,
                                   { x1: p.x1, y1: p.y1, x2: p.x2, y2: p.y2 });
          if (!ends) {
            deps.onStatus?.("A position needs at least X1 and Y1.", true);
            return;
          }
          set(ends);
          deps.onStatus?.(`${p.name} runs ${runOf(ends)}.`);
        }, { feet: true, hint: label.endsWith("2")
              ? "Clear this to make the position run the other way — a blank X2 "
              + "runs it up and downstage, a blank Y2 runs it across."
              : undefined });

      box.appendChild(end("X1", p.x1, "x1"));
      box.appendChild(end("Y1", p.y1, "y1"));
      box.appendChild(end("X2", p.x2, "x2"));
      box.appendChild(end("Y2", p.y2, "y2"));

      // ⭐ THE SAME PIPE, SAID THE OTHER WAY. A truss tower is specified as
      // "20 foot truss, 12 degrees off the wall", not as two coordinates — and
      // working the far end out by hand, then again for every nudge of the
      // angle, is the reason #62 was raised:
      //
      //   "My towers are set at a slight angle to follow the walls... there is
      //    no way to enter an angle for that, without doing some math."
      //
      // These write x2/y2, the same fields the four boxes above write. There is
      // no new state and nothing to keep in step — the length and the angle are
      // READ BACK from the ends every time the panel is built, so whichever way
      // you type, both halves agree.
      const _ends = { x1: p.x1, y1: p.y1, x2: p.x2, y2: p.y2 };
      box.appendChild(field("Length", round2(lengthOf(_ends)), v => {
        const n = num(v);
        if (n === null || n === undefined) return;
        set(endsFromLengthAngle(p.x1, p.y1, n, angleOf(_ends)));
        deps.onStatus?.(`${p.name} is ${fmtFt(n)} long, ${runOf({ ...p, ...endsFromLengthAngle(p.x1, p.y1, n, angleOf(_ends)) })}.`);
      }, { feet: true, hint: "Swings the far end about X1/Y1 — the end you measured from" }));

      // ⚠ NOT parseFeet. An angle is degrees, and "12" must not be read as
      // twelve feet by the length parser sitting next to it.
      box.appendChild(field("Angle", round2(angleOf(_ends)), v => {
        const a = Number(v.trim().replace(/[°\s]/g, ""));
        if (!Number.isFinite(a)) {
          deps.onStatus?.(`"${v}" is not an angle — degrees, so 0 runs across and 90 runs up the deck`, true);
          return;
        }
        const len = lengthOf(_ends);
        if (len < 0.01) {
          deps.onStatus?.("Give the position a length before turning it.", true);
          return;
        }
        set(endsFromLengthAngle(p.x1, p.y1, len, a));
        deps.onStatus?.(`${p.name} is at ${round2(a)}°, ${runOf(endsFromLengthAngle(p.x1, p.y1, len, a))}.`);
      }, { hint: "Degrees. 0 runs across, 90 runs up and downstage. Keeps the length" }));
      if ((p.type ?? "") === "catwalk" || (p.type ?? "") === "truss")
        box.appendChild(field("Width", p.width, v => { const n = num(v);
          if (n === null) return; set({ width: n }); }, { feet: true }));
    }

    const note = document.createElement("p");
    note.className = "muted pos-note";
    const bits: string[] = [];

    // ⭐ SHARING A NAME IS ALLOWED, and is how you say "these two segments are
    // one position" — a V or an L. So this states the consequence rather than
    // warning against it. Everything joins by name, so the segments are already
    // one heading in the schedule and one run of unit numbers.
    //
    // ⚠ The thing that DOES go wrong is the numbering, and it is checked below.
    const sharing = clashes.has(p.name.trim().toLowerCase());
    if (sharing) {
      bits.push(`shares its name with another position — they are one position `
        + `in the schedule and number as one run`);
    }

    // 🔴 THIS is the thing that actually breaks when a name is shared. RP-2
    // §2.3.2 numbers units per POSITION, so unit 1 on two different pipes is
    // right — but a shared name makes those pipes one position, and then two
    // unit 1s are two lights the paperwork cannot tell apart. The schedule, the
    // hookup and the focus chart all address a light as "position, number".
    //
    // ⚠ It is not automatic. `+ unit` takes max+1 across every segment of the
    // name, so it stays unique going forward — but MERGING two pipes that each
    // already had units 1-5 gives 1,1,2,2,3,3,4,4,5.
    //
    // 🔴 AND THE NOTE DOES NOT SEND THE READER TO RENUMBER, which is what it
    // used to do. Jerry, 2026.09.30: "you can't just renumber the units […] you
    // can allow the user to do it, but doing automatically is bad." A unit
    // number is not a label the file owns. It is spiked on the pipe, written in
    // the hookup the electrician is holding, and called out in the dark. Renumber
    // rewrites all of them in the file and none of them in the room. Changing
    // ONE number by hand is the small fix; renumbering the run is a decision
    // about a document that may already have gone out.
    const dupUnits = duplicateUnits(plot.instruments, p.name);
    if (dupUnits.length) {
      bits.push(`🔴 ${dupUnits.length > 1 ? "UNITS" : "UNIT"} `
        + `${dupUnits.join(", ")} ${dupUnits.length > 1 ? "are" : "is"} used twice `
        + `on this position — the paperwork cannot tell them apart. `
        + `Give one of each pair a free number in the inspector`);
    }

    // ⭐ A trim above the ceiling cannot be hung. Nothing checked until
    // 2026.09.24, when a pipe was raised to 18' in a room with a 15' grid and
    // the tool drew it, computed levels from it and printed it without a word.
    const grid = plot.room.gridHeight;
    const foh = p.foh ?? (plot.room.plasterLine !== undefined && p.y1 < plot.room.plasterLine);
    if (p.trim !== undefined && grid !== undefined && !foh) {
      if (p.trim > grid) {
        bits.push(`🔴 ABOVE THE ${grid}' CEILING — this cannot be hung`);
      } else if (p.trim > grid - 1.5) {
        bits.push(`under 1'-6" below the ${grid}' grid — a Source Four and its clamp need about that`);
      }
    }
    if (isVertical(p)) bits.push("vertical — a POINT in plan; units differ by height");
    if (foh) bits.push("front of house — downstage of the plaster line, over the audience");
    if (p.circuits?.length) bits.push(`${p.circuits.length} circuits recorded`);
    else bits.push("no circuits recorded — no load table can be built");
    note.textContent = bits.join(" · ");
    box.appendChild(note);

    const actions = document.createElement("div");
    actions.className = "pos-actions";

    const addUnit = document.createElement("button");
    addUnit.textContent = "+ unit";
    addUnit.title = "Hang a unit on this position, at its trim";
    addUnit.addEventListener("click", () => {
      const name = p.name.trim().toLowerCase();
      const on = plot.instruments.filter(
        i => (i.position ?? "").trim().toLowerCase() === name);
      // ⭐ Copy the LAST unit on this pipe. A designer hanging a wash hangs the
      // same thing six times; starting from a blank one every time would be six times
      // the typing for no gain. Falls back to the plot's most recent unit.
      const model = on[on.length - 1] ?? plot.instruments[plot.instruments.length - 1];
      const nextUnit = on.length ? Math.max(...on.map(i => i.unit)) + 1 : 1;
      const nextCh = plot.instruments.length
        ? Math.max(...plot.instruments.map(i => i.channel ?? 0)) + 1 : 1;
      // ⭐ Drop it in the BIGGEST GAP on the pipe, not at the midpoint.
      //
      // Dropping at the midpoint every time stacks the second unit on top of
      // the first — which the renumber guard caught immediately: "two units
      // share a coordinate, so their order is arbitrary". Filling the largest
      // gap is also what a designer does: the hole in the wash is where the
      // next unit goes.
      let mid: { x: number; y: number };
      // 🔴 A BOOM UNIT NEEDS A HEIGHT, and a boom has no trim to borrow.
      //
      // Jerry, 2026.09.24: "adding an instrument to a boom doesn't seem to
      // work." It did add one — with `height: p.trim`, and a boom position
      // record carries no trim, so the height was undefined. An undefined
      // height puts a unit in the elevation's NO HEIGHT RECORDED list and skips
      // it in plan, so the unit existed in the file and appeared on neither
      // drawing: exactly "doesn't work".
      //
      // ⚠ Added BELOW the lowest, not in the biggest gap like a pipe. On a boom
      // the numbers run top down — the sample is 1 at 12'-0", 2 at 8'-0", 3 at
      // 4'-6" — so going downwards keeps max(unit)+1 the RIGHT number and needs
      // no renumber. Dropping one into a middle gap would number it last and
      // read wrong on the elevation.
      let height: number | undefined;
      if (isVertical(p)) {
        mid = { x: p.x1, y: p.y1 };
        height = nextBoomHeight(on.map(i => i.height), p.trim);
        if (height === undefined) {
          // ⚠ Refuse rather than stack. Two units at one height on a boom are
          // indistinguishable on the elevation AND in plan, where a boom is a
          // point — so the drawing would show one unit and the paperwork two,
          // and nothing would say which was which.
          deps.onStatus?.(
            `${p.name} has no room for another unit — every gap is under a foot. `
            + `Move one, or raise the top of the boom.`, true);
          return;
        }
            } else {
        const horizontal = Math.abs(p.x2 - p.x1) >= Math.abs(p.y2 - p.y1);
        const along = (i: { x: number; y: number }) => (horizontal ? i.x : i.y);
        const a = horizontal ? p.x1 : p.y1;
        const b = horizontal ? p.x2 : p.y2;
        const lo = Math.min(a, b), hi = Math.max(a, b);
        // the pipe ends count as edges of the first and last gap
        const marks = [lo, ...on.map(along).sort((m, n) => m - n), hi];
        let best = lo + (hi - lo) / 2, widest = -1;
        for (let k = 0; k < marks.length - 1; k++) {
          const gap = marks[k + 1]! - marks[k]!;
          if (gap > widest) { widest = gap; best = marks[k]! + gap / 2; }
        }
        mid = horizontal
          ? { x: best, y: (p.y1 + p.y2) / 2 }
          : { x: (p.x1 + p.x2) / 2, y: best };
      }
      const outOfOrder = isVertical(p) && height !== undefined
        && on.some(i => i.height !== undefined && i.height < height!);
      store.add({
        unit: nextUnit,
        channel: nextCh,
        type: model?.type ?? "S4 26",
        x: mid.x, y: mid.y,
        // On a vertical position the hang height IS the trim — one number,
        // written to both, because booms.py reads `height` and the photometrics
        // read `trim`.
        trim: isVertical(p) ? height : p.trim,
        ...(isVertical(p) ? { height } : {}),
        position: p.name,
        color: model?.color,
        lamp: model?.lamp,
        focusX: model?.focusX, focusY: model?.focusY,
      });
      if (outOfOrder) {
        // ⚠ Say it. A unit numbered 5 sitting between 2 and 3 on the elevation
        // is a paperwork error waiting to happen.
        //
        // It used to end "press renumber on X". It no longer tells anyone to do
        // that — see the note on duplicate units above. State the fact and let
        // the designer decide whether the order is worth rewriting the run for;
        // on a boom that is still being built it usually is not.
        deps.onStatus?.(
          `Unit ${nextUnit} went in above a lower one, so ${p.name} is not in `
          + `numerical order down the boom.`);
      }
      deps.onChange();
    });
    actions.appendChild(addUnit);

    const del = document.createElement("button");
    del.textContent = "delete";
    del.className = "danger";
    del.addEventListener("click", () => {
      const idx = plot.positions.indexOf(p);
      const name = p.name.trim().toLowerCase();
      const on = plot.instruments.filter(
        i => (i.position ?? "").trim().toLowerCase() === name).length;
      // ⚠ ALWAYS ask, not only when units hang on it. An empty pipe used to
      // vanish on one click, and a position carries its trim, its width, its
      // circuits and its mount — none of which is obvious from the row, and all
      // of which is typing to get back.
      if (!confirmDelete(
        `the position ${p.name}`,
        on ? `${on} unit${on > 1 ? "s" : ""} on it will be KEPT, but lose their position.`
           : undefined)) return;
      const orphaned = store.removePosition(idx);
      if (orphaned.length) {
        alert(`${p.name} deleted. ${orphaned.join(", ")} now ` +
              `${orphaned.length > 1 ? "have" : "has"} no position — ` +
              `reassign ${orphaned.length > 1 ? "them" : "it"} in the inspector.`);
      }
      deps.onChange();
    });
    actions.appendChild(del);

    const renumberBtn = document.createElement("button");
    renumberBtn.textContent = "renumber";
    renumberBtn.title = "Renumber the units on this position, per RP-2 §2.3.2";
    renumberBtn.addEventListener("click", async () => {
      try {
        const r = await renumber(plot, p);
        if (r.warning) { alert(r.warning); return; }
        if (!r.count) { alert(`${p.name} has no units on it.`); return; }
        if (!r.changed) { alert(`${p.name} is already numbered correctly.\n\n${r.convention}`); return; }
        // ⚠ SHOW the moves and ask. A renumber on a plot that has been hung
        // produces a different document from the one taped to the pipe, and a
        // reader cannot tell 1-to-6 from 6-to-1 by looking at a single number.
        const lines = r.moves.slice(0, 12)
          .map(m => `   unit ${m.from} → ${m.to}`).join("\n");
        const more = r.moves.length > 12 ? `\n   …and ${r.moves.length - 12} more` : "";
        // 🔴 A shared name is two legs ordered by ONE leg's geometry, which
        // interleaves them when they cover the same ground. Say so above the
        // moves — the reader still decides. See `sharedNameRenumberNote`.
        const legs = plot.positions.filter(
          q => q.name.trim().toLowerCase() === p.name.trim().toLowerCase()).length;
        const shared = legs > 1 ? `${sharedNameRenumberNote(p.name, legs)}\n\n` : "";
        if (!confirm(`${shared}${r.convention}\n\n${r.changed} of ${r.count} units change:\n${lines}${more}\n\nApply?`)) return;
        store.begin(null);
        const byPos = new Map(r.instruments.map(i => [`${i.x},${i.y},${i.height ?? ""}`, i.unit]));
        const name = p.name.trim().toLowerCase();
        for (const inst of plot.instruments) {
          if ((inst.position ?? "").trim().toLowerCase() !== name) continue;
          const k = `${inst.x},${inst.y},${inst.height ?? ""}`;
          const u = byPos.get(k);
          if (u !== undefined) inst.unit = u;
        }
        store.commit();
        deps.onChange();
      } catch (e) {
        alert(e instanceof Error ? e.message : String(e));
      }
    });
    actions.appendChild(renumberBtn);

    // ⭐ Jerry, 2026.09.30: "pick a starting sequence number and then letting the
    // user fix the sequence by selecting units." It sits BESIDE renumber rather
    // than replacing it: renumber is one click when §2.3.2's order is the right
    // one, and this is for when it is not — a V, a curved cove, or a rig
    // somebody else hung. See `sequence.ts`.
    if (deps.onNumberSeq) {
      const seqBtn = document.createElement("button");
      seqBtn.textContent = "number by clicking";
      seqBtn.title = "Pick a starting number, then click the units in hanging order";
      seqBtn.addEventListener("click", () => {
        const units = plot.instruments.filter(
          i => (i.position ?? "").trim().toLowerCase() === p.name.trim().toLowerCase()).length;
        if (!units) { alert(`${p.name} has no units on it.`); return; }
        // ⚠ Default 1, not max+1. A pass usually renumbers a run from the top;
        // offering the number after the highest would silently continue a run
        // the designer is trying to rewrite.
        const raw = window.prompt(
          `Number ${units} unit${units > 1 ? "s" : ""} on ${p.name}, starting at:`, "1");
        if (raw === null) return;
        const start = Number(raw.trim());
        if (!Number.isInteger(start) || start < 1) {
          alert(`"${raw.trim()}" is not a unit number. Give a whole number, 1 or more.`);
          return;
        }
        deps.onNumberSeq?.(p, start);
      });
      actions.appendChild(seqBtn);
    }

    box.appendChild(actions);

    host.appendChild(box);
  });

  const addPos = document.createElement("button");
  addPos.textContent = "+ Add position";
  addPos.addEventListener("click", () => {
    // ⭐ THE USER NAMES IT. The old button invented `Electric ${count + 1}`,
    // which is one delete away from a collision — the demo ships seven
    // positions, one called "Electric 7", so deleting any of them and pressing
    // add produced a second "Electric 7" silently.
    //
    // ⚠ And a clash is ALLOWED, because it is a real thing to want. A V or an L
    // is one position made of two straight segments; sharing the name is how
    // you say so, and the plot already treats them as one for numbering and
    // paperwork. So: suggest a free name, say plainly when the typed one is
    // taken and what that means, and let them go ahead.
    const suggested = nextPositionName(plot.positions);
    const typed = window.prompt("Name this position", suggested);
    if (typed === null) return;                       // cancelled; add nothing
    const wanted = typed.trim();
    if (!wanted) {
      deps.onStatus?.("A position needs a name.", true);
      return;
    }
    const clashes = plot.positions.filter(
      q => q.name.trim().toLowerCase() === wanted.toLowerCase()).length;
    if (clashes && !confirmSharedName(wanted, clashes)) return;
    const n = plot.positions.length + 1;
    store.addPosition({
      name: wanted,
      type: "electric",
      x1: 0, y1: Math.min(plot.room.depth - 2, 8 + n * 4),
      x2: plot.room.width, y2: Math.min(plot.room.depth - 2, 8 + n * 4),
      trim: plot.room.gridHeight !== undefined
        ? Math.max(0, plot.room.gridHeight - 2) : undefined,
    });
    deps.onChange();
  });
  host.appendChild(addPos);
}
