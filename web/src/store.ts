/**
 * One plot, one selection, one undo stack. Both views read from here.
 *
 * Deliberately small: a plot is a few dozen instruments, so the whole thing is
 * cloned on every edit and history is just an array of snapshots. No diffing,
 * no proxies, nothing to debug at two in the morning during a tech.
 */
import type { Plot, Instrument, Position, Room } from "./plot.js";

export type Listener = () => void;

/** A snapshot is the plot plus which unit was selected when it was taken, so
 *  undo puts the selection back where the eye expects it — and the revision it
 *  was taken at, which is what lets `dirty` answer honestly. See `_seq`. */
interface Snapshot { plot: Plot; selected: number | null; seq: number }

/** Is this patch actually saying anything new?
 *
 *  ⚠ null and undefined are the SAME ANSWER here. The inspector writes
 *  `undefined` for an emptied box and the .plot.json may hold `null` for a
 *  field nobody filled, so treating them as different would make clearing an
 *  already-empty field count as an edit — which is the exact bug this guards. */
function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if ((a === undefined || a === null) && (b === undefined || b === null)) return true;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => v === b[i]);
  }
  return false;
}

const HISTORY_LIMIT = 200;

export class Store {
  private _plot: Plot;
  private _selected: number | null = null;      // index into instruments
  private _selectedPosition: number | null = null;   // index into positions
  private _undo: Snapshot[] = [];
  private _redo: Snapshot[] = [];
  // ⭐ DIRTY IS A DIFFERENCE, NOT AN ACTIVITY. `_seq` counts real changes to the
  // document and `_savedSeq` remembers where it stood when the file was
  // written, so `dirty` asks "does this differ from disk?" rather than "did the
  // user touch something?". Undo restores the seq along with the plot, which is
  // what makes undoing back to the saved state go clean again.
  //
  // Jerry, 2026.09.29: "if someone selects a light and does nothing to it,
  // should the plot be considered changed?" No — and nor should setting a field
  // to the value it already had. See docs/DECISIONS.md.
  private _seq = 0;
  private _savedSeq = 0;
  // What the last begin() did, so an edit that turns out to change nothing can
  // put the history back exactly as it found it.
  private lastBegin: { pushed: boolean; prevKey: string | null; redo: Snapshot[] } | null = null;
  private listeners = new Set<Listener>();

  constructor(plot: Plot) {
    this._plot = plot;
  }

  get plot(): Plot { return this._plot; }
  get selected(): number | null { return this._selected; }

  /** Which POSITION is current, as an index into `positions`.
   *
   *  ⭐ #78: "it's hard to tell when a position is selected." There was nothing
   *  to tell — `_selected` has always been an index into INSTRUMENTS, and a
   *  position could not be selected, clicked or pointed at. This is the missing
   *  half, not a colour change.
   */
  get selectedPosition(): number | null { return this._selectedPosition; }
  get selectedInstrument(): Instrument | null {
    return this._selected === null ? null : this._plot.instruments[this._selected] ?? null;
  }
  get dirty(): boolean { return this._seq !== this._savedSeq; }
  get canUndo(): boolean { return this._undo.length > 0; }
  get canRedo(): boolean { return this._redo.length > 0; }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(): void { for (const fn of this.listeners) fn(); }

  private snapshot(): Snapshot {
    return { plot: structuredClone(this._plot), selected: this._selected, seq: this._seq };
  }

  /** One real change happened. */
  private touch(): void {
    this._seq++;
    this.lastBegin = null;   // that begin() is spoken for; it cannot be undone now
  }

  /** The edit after begin() turned out to change nothing — put history back.
   *
   *  ⚠ If that push evicted the oldest entry at HISTORY_LIMIT, the eviction
   *  stands: popping our own entry cannot bring it back. Two hundred edits deep
   *  it is not worth a second data structure to avoid. */
  private cancelBegin(): void {
    const b = this.lastBegin;
    this.lastBegin = null;
    if (!b) return;
    if (b.pushed) {
      this._undo.pop();
      this._redo = b.redo;
    }
    this.lastKey = b.prevKey;
  }

  /**
   * Take a history entry before changing anything.
   *
   * `coalesceKey` merges consecutive edits of the same kind — one drag is one
   * undo step, not two hundred. Pass null to force a new entry.
   */
  private lastKey: string | null = null;
  begin(coalesceKey: string | null = null): void {
    const prevKey = this.lastKey;
    if (coalesceKey !== null && coalesceKey === this.lastKey) {
      this.lastBegin = { pushed: false, prevKey, redo: this._redo };
      return;
    }
    const redo = this._redo;
    this._undo.push(this.snapshot());
    if (this._undo.length > HISTORY_LIMIT) this._undo.shift();
    // ⚠ A NEW ARRAY, not `.length = 0`. cancelBegin() hands the old one back,
    // so an edit that changes nothing must not have emptied it on the way past:
    // undo, then tab through a field without altering it, and redo still works.
    this._redo = [];
    this.lastKey = coalesceKey;
    this.lastBegin = { pushed: true, prevKey, redo };
  }

  /** End a coalescing run, so the next edit starts a fresh undo entry. */
  commit(): void { this.lastKey = null; }

  select(index: number | null): void {
    // ⚠ ONE THING IS CURRENT AT A TIME. A unit and a pipe highlighted together
    // leaves two answers to "what am I looking at", and the inspector can only
    // show one of them anyway. Picking a unit means you are now on the unit.
    //
    // 🔴 THE EARLY RETURN HAS TO ASK ABOUT BOTH. `if (this._selected === index)
    // return` alone skipped the clearing whenever the unit was ALREADY current
    // — which `add()` makes the normal case, since adding a unit selects it. So
    // selecting a pipe, adding a unit to it, then clicking that unit left the
    // pipe lit as well. Caught by the test, not by reading.
    const same = this._selected === index
      && !(index !== null && this._selectedPosition !== null);
    if (same) return;
    this._selected = index;
    if (index !== null) this._selectedPosition = null;
    this.emit();
  }

  /** Make a position current. Mutually exclusive with the instrument selection,
   *  for the reason in `select`. */
  selectPosition(index: number | null): void {
    if (this._selectedPosition === index) return;
    this._selectedPosition = index;
    if (index !== null) this._selected = null;
    this.emit();
  }

  /** Change fields on one instrument. Caller calls begin() first.
   *
   *  ⭐ A PATCH THAT SAYS NOTHING NEW IS NOT AN EDIT. Typing a value back the
   *  way it was, tabbing out of a field you only looked at, or dragging a unit
   *  and dropping it where it started all arrive here — and all used to mark
   *  the plot changed, push a dead undo entry and throw away the redo stack.
   *  The undo entry was the worst of the three: you press undo, nothing moves,
   *  and you press it again. */
  update(index: number, patch: Partial<Instrument>): void {
    const inst = this._plot.instruments[index];
    if (!inst) return;
    const keys = Object.keys(patch) as (keyof Instrument)[];
    if (keys.every(k => same(inst[k], patch[k]))) {
      this.cancelBegin();
      return;
    }
    Object.assign(inst, patch);
    this.touch();
    this.emit();
  }

  add(inst: Instrument): number {
    this.begin(null);
    this._plot.instruments.push(inst);
    this._selected = this._plot.instruments.length - 1;
    this.touch();
    this.emit();
    return this._selected;
  }

  /** Add a position. Returns its index.
   *
   * ⚠ Positions had no add or remove at all — a boom or a catwalk could only be
   * created by hand-editing the .plot.json, which meant the editor could not
   * build a plot, only adjust one somebody else had written.
   */
  addPosition(pos: Position): number {
    this.begin(null);
    this._plot.positions.push(pos);
    this.touch();
    this.emit();
    return this._plot.positions.length - 1;
  }

  /** Remove a position. Instruments hung on it are NOT deleted — they are
   *  orphaned and reported, because losing a unit because a pipe was deleted is
   *  a much worse surprise than a unit with no position. */
  removePosition(index: number): string[] {
    // ⚠ A stale index outlives the thing it pointed at. Clearing it here rather
    // than at the call site means every route to delete is covered.
    if (this._selectedPosition === index) this._selectedPosition = null;
    else if (this._selectedPosition !== null && this._selectedPosition > index) this._selectedPosition--;
    const pos = this._plot.positions[index];
    if (!pos) return [];
    const name = pos.name.trim().toLowerCase();
    const orphaned = this._plot.instruments
      .filter(i => (i.position ?? "").trim().toLowerCase() === name)
      .map(i => `unit ${i.unit}`);
    this.begin(null);
    this._plot.positions.splice(index, 1);
    for (const inst of this._plot.instruments) {
      if ((inst.position ?? "").trim().toLowerCase() === name) inst.position = undefined;
    }
    this.touch();
    this.emit();
    return orphaned;
  }

  /** Change the plot's own fields — show, venue, designer, studio, revision.
   *
   * ⭐ These had NO WAY IN but hand-editing the .plot.json, and on 2026.09.24
   * they started to matter: the renderer stopped hardcoding "Twin Oaks Studios"
   * and "Design: Jerry Jonas", so a title block now says whatever the file
   * says. Without somewhere to type them, the only way to stop a new plot
   * printing nothing — or the wrong name — was a text editor.
   */
  setMeta(patch: Partial<Plot>): void {
    this.begin(null);
    Object.assign(this._plot, patch);
    this.touch();
    this.emit();
  }

  /** Change a line weight. Points on paper, so the value means the same at
   *  every scale. Clearing a field REMOVES the override rather than storing a
   *  zero — a zero-width line is not a thin line, it is an invisible one. */
  setWeight(path: "light" | "medium" | "heavy" | `positions.${string}` | `styles.${string}`,
            value: number | undefined): void {
    this.begin(null);
    const w = (this._plot.lineWeights ??= {});
    const [head, key] = path.split(".") as [string, string | undefined];
    if (key === undefined) {
      if (value === undefined) delete (w as Record<string, unknown>)[head];
      else (w as Record<string, unknown>)[head] = value;
    } else {
      const group = ((w as Record<string, Record<string, number>>)[head] ??= {});
      if (value === undefined) delete group[key];
      else group[key] = value;
      if (Object.keys(group).length === 0) delete (w as Record<string, unknown>)[head];
    }
    // An empty override block is noise in the file; drop it.
    if (Object.keys(w).length === 0) delete this._plot.lineWeights;
    this.touch();
    this.emit();
  }

  /** Change the room. ⚠ Every one of these moves the DRAWING, not just a label:
   *  width and depth resize it, the grid height and house ceiling are what
   *  trims are checked against, and the plaster line decides which positions
   *  are front of house. The caller has to recompute, not just redraw. */
  setRoom(patch: Partial<Room>): void {
    this.begin(null);
    Object.assign(this._plot.room, patch);
    this.touch();
    this.emit();
  }

  remove(index: number): void {
    if (!this._plot.instruments[index]) return;
    this.begin(null);
    this._plot.instruments.splice(index, 1);
    if (this._selected !== null && this._selected >= this._plot.instruments.length) {
      this._selected = this._plot.instruments.length ? this._plot.instruments.length - 1 : null;
    }
    this.touch();
    this.emit();
  }

  undo(): void {
    const s = this._undo.pop();
    if (!s) return;
    this._redo.push(this.snapshot());
    this._plot = s.plot;
    this._selected = s.selected;
    // ⭐ The revision comes back with the plot, so stepping back to where the
    // file was written reports CLEAN. It used to assert dirty unconditionally:
    // you could undo your way to exactly what was on disk and still be told
    // there was something to lose.
    this._seq = s.seq;
    this.lastBegin = null;
    this.lastKey = null;
    this.emit();
  }

  redo(): void {
    const s = this._redo.pop();
    if (!s) return;
    this._undo.push(this.snapshot());
    this._plot = s.plot;
    this._selected = s.selected;
    // ⭐ The revision comes back with the plot, so stepping back to where the
    // file was written reports CLEAN. It used to assert dirty unconditionally:
    // you could undo your way to exactly what was on disk and still be told
    // there was something to lose.
    this._seq = s.seq;
    this.lastBegin = null;
    this.lastKey = null;
    this.emit();
  }

  markSaved(): void { this._savedSeq = this._seq; this.emit(); }

  /**
   * Put the plot back to `plot`, which is what is on disk.
   *
   * ⭐ #56: "a revert to return the file to the way it was before we touched it
   * in this session - save the state before we open it." Most of it was already
   * here: `adoptPlot` builds a fresh Store from the loaded plot and `dirty` is
   * literally `_seq !== _savedSeq`. What was missing is KEEPING that plot, so
   * going back is one step rather than a walk up the undo stack.
   *
   * ⚠ IT IS UNDOABLE. A revert that cannot be taken back is a second way to
   * lose an afternoon, and this store already has the machinery — so the
   * snapshot goes on the undo stack like any other edit.
   *
   * 🔴 AND IT ENDS CLEAN. `_savedSeq` is moved to meet `_seq`, because the plot
   * now matches the file. Bumping the sequence without that would leave the
   * editor claiming unsaved changes against a document it had just restored —
   * and "Revert" that leaves you dirty is not a word that means anything.
   */
  revertTo(plot: Plot): void {
    this._undo.push(this.snapshot());
    if (this._undo.length > HISTORY_LIMIT) this._undo.shift();
    this._redo = [];
    this.lastKey = null;
    this.lastBegin = null;
    this._plot = structuredClone(plot);
    this._seq++;
    this._savedSeq = this._seq;
    this._selected = null;
    this._selectedPosition = null;
    this.emit();
  }
}

/**
 * Snap a dragged point to a hanging position.
 *
 * Instruments hang on pipes. A unit sitting at y = 20.3 when the pipe is at 20
 * is wrong on paper and wrong in the room, and nobody notices until the plot is
 * printed. Within `threshold` feet the point lands on the line and the
 * instrument's `position` is set to that pipe's name.
 *
 * Returns the snapped point and the position name, or the original point and
 * null when nothing is near.
 */
export function snapToPosition(
  x: number, y: number, plot: Plot, threshold = 1.0,
): { x: number; y: number; position: string | null } {
  let best: { x: number; y: number; position: string; d: number } | null = null;
  for (const p of plot.positions) {
    const dx = p.x2 - p.x1, dy = p.y2 - p.y1;
    const lenSq = dx * dx + dy * dy;
    // projection of the point onto the segment, clamped to its ends
    const t = lenSq === 0 ? 0 : Math.max(0, Math.min(1, ((x - p.x1) * dx + (y - p.y1) * dy) / lenSq));
    const px = p.x1 + t * dx, py = p.y1 + t * dy;
    const d = Math.hypot(x - px, y - py);
    if (d <= threshold && (!best || d < best.d)) best = { x: px, y: py, position: p.name, d };
  }
  return best ? { x: best.x, y: best.y, position: best.position } : { x, y, position: null };
}
