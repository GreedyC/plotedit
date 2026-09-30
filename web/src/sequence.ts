/**
 * Numbering a run by pointing at the units, one at a time, in the order they
 * hang.
 *
 * ⭐ Jerry, 2026.09.30: "One cool feature Vectorworks has is the ability to pick
 * a starting sequence number and then letting the user fix the sequence by
 * selecting units."
 *
 * 🔴 THIS IS THE ANSWER TO A QUESTION THE APP COULD NOT ANSWER. `positions.order`
 * derives one sort key from geometry — stage left to stage right per RP-2
 * §2.3.2 — and on a bent position it is simply wrong: a V whose legs cover the
 * same ground gets odds down one leg and evens back up the other, because one
 * key cannot order two legs. `docs/NEXT.md` asks which leg comes first and which
 * end of each leg starts, and notes RP-2 §2.3.2 does not cover a bent position.
 *
 * **Clicking removes the question instead of answering it.** The order is
 * whatever order the designer walks the pipe in, which is the only authority
 * there was ever going to be. No convention to derive, and it works on a V, an
 * L, a curved cove and a rig hung by somebody else's logic.
 *
 * ⚠ AND IT OBEYS THE RULE THAT THE SORT-BASED RENUMBER BROKE. Jerry, the same
 * day: "you can't just renumber the units […] you can allow the user to do it,
 * but doing automatically is bad." Every number here comes from a click. Nothing
 * is derived, nothing runs by itself, and each click is its own undo step so a
 * misclick costs one ⌘Z rather than the run.
 *
 * This module is the DECISION ONLY. It never touches the plot — the caller
 * applies the number and owns undo — so the rules can be tested without a
 * browser.
 */

/** A numbering pass in progress. */
export interface Seq {
  /** The run being numbered, by NAME. A V is two positions sharing one name and
   *  is therefore ONE run — which is exactly the case sort-based renumbering
   *  gets wrong. */
  readonly name: string;
  /** The number the next click will assign. */
  next: number;
  readonly step: number;
  /** Instrument indices already numbered in THIS pass. */
  readonly done: Map<number, { from?: number; to: number }>;
}

export interface SeqUnit {
  position?: string;
  unit?: number;
}

export function startSeq(name: string, start: number, step = 1): Seq {
  return { name, next: start, step, done: new Map() };
}

const key = (s?: string) => (s ?? "").trim().toLowerCase();

/** Every index on the run, in file order. */
export function runIndices(instruments: readonly SeqUnit[], name: string): number[] {
  const k = key(name);
  const out: number[] = [];
  instruments.forEach((i, n) => { if (key(i.position) === k) out.push(n); });
  return out;
}

export type SeqClick =
  | { ok: true; index: number; from?: number; to: number; next: number; last: boolean }
  | { ok: false; why: string };

/** Decide what a click on `index` does. Advances the pass when it succeeds.
 *
 *  ⚠ REFUSES A SECOND CLICK ON THE SAME UNIT. A pointerdown fires twice on a
 *  double click, and silently taking the next number for a unit that already has
 *  one leaves a GAP in the sequence that nobody would see until the hookup came
 *  out wrong.
 */
export function seqClick(
  seq: Seq, instruments: readonly SeqUnit[], index: number,
): SeqClick {
  const inst = instruments[index];
  if (!inst) return { ok: false, why: "that unit is no longer in the plot" };
  if (key(inst.position) !== key(seq.name)) {
    return {
      ok: false,
      why: `that unit is on ${inst.position ? `"${inst.position}"` : "no position"}`
         + `, not "${seq.name}" — numbers run per position, RP-2 §2.3.2`,
    };
  }
  const already = seq.done.get(index);
  if (already) {
    return { ok: false, why: `already numbered ${already.to} in this pass` };
  }
  const to = seq.next;
  const from = inst.unit;
  seq.done.set(index, { from, to });
  seq.next = to + seq.step;
  const remaining = runIndices(instruments, seq.name)
    .filter(i => !seq.done.has(i)).length;
  return { ok: true, index, from, to, next: seq.next, last: remaining === 0 };
}

/** What to show after one click. `from` is stated because a number being
 *  OVERWRITTEN is the whole risk — see the rule quoted at the top. */
export function clickLine(r: Extract<SeqClick, { ok: true }>): string {
  const was = r.from === undefined ? "unnumbered" : `unit ${r.from}`;
  return r.last
    ? `${was} → ${r.to}. That is every unit on the run.`
    : `${was} → ${r.to}. Next: ${r.next}. Escape to stop, ⌘Z to undo one.`;
}

/** The verdict when the pass ends, however it ends.
 *
 *  🔴 DUPLICATES ARE ONLY REPORTED AT THE END, NEVER DURING. Mid-pass duplicates
 *  are NORMAL and resolve themselves: on a run of units 1-5 being reordered, the
 *  first click makes some unit 1 while the original unit 1 is still unclicked and
 *  still holds 1. Warning there would fire on essentially every pass, which is
 *  how a warning stops being read.
 *
 *  ⚠ An ABANDONED pass is the case that genuinely leaves a broken run, and it is
 *  the one this reports — partly numbered, with duplicates, and visible.
 */
export function seqReport(seq: Seq, instruments: readonly SeqUnit[]): string {
  const all = runIndices(instruments, seq.name);
  const numbered = seq.done.size;
  if (!numbered) return `${seq.name}: nothing was numbered.`;

  const left = all.filter(i => !seq.done.has(i));
  const counts = new Map<number, number>();
  for (const i of all) {
    const u = instruments[i]?.unit;
    if (u !== undefined) counts.set(u, (counts.get(u) ?? 0) + 1);
  }
  const dups = [...counts.entries()].filter(([, n]) => n > 1)
    .map(([u]) => u).sort((a, b) => a - b);

  const bits = [`${seq.name}: numbered ${numbered} unit${numbered > 1 ? "s" : ""}`];
  if (left.length) {
    bits.push(`${left.length} still ${left.length > 1 ? "have" : "has"} `
      + `${left.length > 1 ? "their old numbers" : "its old number"}`);
  }
  if (dups.length) {
    bits.push(`🔴 ${dups.length > 1 ? "numbers" : "number"} ${dups.join(", ")} `
      + `${dups.length > 1 ? "are" : "is"} now used twice — the paperwork cannot `
      + `tell those units apart`);
  }
  return bits.join("; ") + ".";
}
