/**
 * Pointer handling on the drawing: click to select, drag to move.
 *
 * Two things are draggable — the instrument itself and its focus point. The
 * focus point is a separate handle because aiming a unit and moving it are
 * different decisions, and conflating them is how a focus gets lost while
 * tidying a hang.
 *
 * A whole drag is ONE undo step, via the store's coalesce key.
 */
import { toPlot, type View } from "./geometry.js";
import { Store, snapToPosition } from "./store.js";
import { confirmDelete, describeUnit } from "./confirm.js";

export interface DragContext {
  /** Current view, read fresh on every pointerdown — it changes with zoom. */
  view: () => View;
  /** Redraw. Called on every move; the caller decides how to be cheap about it. */
  onChange: () => void;
  /** Called once when a drag ends, so the caller can recompute against the server. */
  onSettled: () => void;
  onPanStart?: () => void;
  onPan?: (dx: number, dy: number) => void;
}

/** "elevation" is a unit drawn in a §6.12 boom elevation: selectable, but not
 *  draggable — that diagram's coordinates are not plan coordinates. */
type Handle = "body" | "focus" | "elevation";

/** Which handle a press grabs.
 *
 * ⭐ SHIFT on a unit's body grabs its FOCUS (Jerry, 2026.10.09). A unit
 * focused straight down — a downlight — has its focus point under its own
 * body, and the body is drawn on top, so the ring could not be grabbed at all.
 * Shift reaches it wherever the focus is. Alt was taken (off-pipe placement).
 */
export function pickHandle(dataHandle: string | null, shiftKey: boolean): Handle {
  const h = (dataHandle ?? "body") as Handle;
  return h === "body" && shiftKey ? "focus" : h;
}

const pointerControllers = new WeakMap<SVGSVGElement, AbortController>();

export function attachPointer(svg: SVGSVGElement, store: Store, ctx: DragContext): void {
  pointerControllers.get(svg)?.abort();
  const controller = new AbortController();
  pointerControllers.set(svg, controller);
  const options = { signal: controller.signal };
  let panning: { id: number; x: number; y: number; cursor: string; moved: boolean } | null = null;
  let dragging: { id: number; index: number; handle: Handle; dx: number; dy: number } | null = null;

  controller.signal.addEventListener("abort", () => {
    if (panning) {
      svg.style.cursor = panning.cursor;
      try { svg.releasePointerCapture(panning.id); } catch { /* already gone */ }
      panning = null;
    }
    if (dragging) {
      store.commit();
      try { svg.releasePointerCapture(dragging.id); } catch { /* already gone */ }
      dragging = null;
    }
  });

  const plotPointFromEvent = (e: PointerEvent) => {
    const r = svg.getBoundingClientRect();
    return toPlot({ x: e.clientX - r.left, y: e.clientY - r.top }, ctx.view());
  };

  svg.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || panning || dragging) return;
    const target = e.target as Element | null;
    const hit = target?.closest("[data-index]") as SVGElement | null;
    if (!hit) {
      // ⭐ #78. A pipe is a thing you can point at now. Asked AFTER the unit,
      // because a unit sits on top of its position and the one under the
      // pointer is the one meant — clicking a light should never select the
      // pipe it hangs from.
      const pos = target?.closest("[data-position]") as SVGElement | null;
      if (pos) {
        store.selectPosition(Number(pos.getAttribute("data-position")));
        e.preventDefault();
        return;
      }
      if (ctx.onPan) {
        ctx.onPanStart?.();
        panning = { id: e.pointerId, x: e.clientX, y: e.clientY, cursor: svg.style.cursor, moved: false };
        svg.style.cursor = "grabbing";
        svg.setPointerCapture(e.pointerId);
        e.preventDefault();
      } else {
        store.select(null);
        store.selectPosition(null);
      }
      return;
    }

    const index = Number(hit.getAttribute("data-index"));
    const handle = pickHandle(hit.getAttribute("data-handle"), e.shiftKey);
    store.select(index);

    // ⚠ A unit in a BOOM ELEVATION can be selected but not dragged. The
    // elevation is a diagram beside the plot, not the plot: its x is which boom
    // this is and its y is a COMPRESSED height, so dragging there would write a
    // plan position the reader never pointed at.
    if (handle === "elevation") { e.preventDefault(); return; }

    const inst = store.plot.instruments[index];
    if (!inst) return;
    const p = plotPointFromEvent(e);
    // Keep the grab offset so the symbol does not jump to the cursor.
    dragging = handle === "focus"
      ? { id: e.pointerId, index, handle, dx: (inst.focusX ?? p.x) - p.x, dy: (inst.focusY ?? p.y) - p.y }
      : { id: e.pointerId, index, handle, dx: inst.x - p.x, dy: inst.y - p.y };
    svg.setPointerCapture(e.pointerId);
    e.preventDefault();
  }, options);

  svg.addEventListener("pointermove", (e) => {
    if (panning) {
      if (e.pointerId !== panning.id) return;
      panning.moved ||= e.clientX !== panning.x || e.clientY !== panning.y;
      ctx.onPan?.(e.clientX - panning.x, e.clientY - panning.y);
      e.preventDefault();
      return;
    }
    if (!dragging || e.pointerId !== dragging.id) return;
    const p = plotPointFromEvent(e);
    const { index, handle, dx, dy } = dragging;
    let x = p.x + dx, y = p.y + dy;

    store.begin(`drag:${index}:${handle}`);
    if (handle === "focus") {
      store.update(index, { focusX: round(x), focusY: round(y) });
    } else {
      // Hold Alt to place a unit off a pipe deliberately.
      if (!e.altKey) {
        const snap = snapToPosition(x, y, store.plot);
        x = snap.x; y = snap.y;
        if (snap.position) store.update(index, { position: snap.position });
      }
      store.update(index, { x: round(x), y: round(y) });
    }
    ctx.onChange();
  }, options);

  const end = (e: PointerEvent) => {
    if (panning) {
      if (e.pointerId !== panning.id) return;
      svg.style.cursor = panning.cursor;
      const deselect = !panning.moved && e.type === "pointerup";
      panning = null;
      if (deselect) { store.select(null); store.selectPosition(null); }
      try { svg.releasePointerCapture(e.pointerId); } catch { /* already gone */ }
      return;
    }
    if (!dragging || e.pointerId !== dragging.id) return;
    dragging = null;
    store.commit();
    try { svg.releasePointerCapture(e.pointerId); } catch { /* already gone */ }
    ctx.onSettled();
  };
  svg.addEventListener("pointerup", end, options);
  svg.addEventListener("pointercancel", end, options);
  svg.addEventListener("lostpointercapture", end, options);
}

/** Feet to the nearest inch. Sub-inch precision on a light plot is a lie. */
function round(feet: number): number {
  return Math.round(feet * 12) / 12;
}

/** Arrow keys nudge, Delete removes, Escape deselects, cmd/ctrl-Z undoes. */
export function attachKeyboard(store: Store, ctx: DragContext): void {
  window.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement | null;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;   // typing, not driving

    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === "z") {
      e.preventDefault();
      e.shiftKey ? store.redo() : store.undo();
      ctx.onChange(); ctx.onSettled();
      return;
    }

    const i = store.selected;
    if (i === null) return;

    if (e.key === "Escape") { store.select(null); return; }
    if (e.key === "Delete" || e.key === "Backspace") {
      // 🔴 This was the worst of the three: one keystroke, no dialog, and
      // Backspace is a key people press out of habit when a field is not
      // focused. It asks now like every other delete.
      e.preventDefault();
      const inst = store.plot.instruments[i];
      if (inst && !confirmDelete(describeUnit(inst))) return;
      store.remove(i);
      ctx.onChange(); ctx.onSettled();
      return;
    }

    const step = e.shiftKey ? 1 : 1 / 12;      // a foot, or an inch
    const d: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0], ArrowRight: [step, 0],
      ArrowUp: [0, step], ArrowDown: [0, -step],       // up the screen is upstage
    };
    const move = d[e.key];
    if (!move) return;
    e.preventDefault();
    const inst = store.plot.instruments[i];
    if (!inst) return;
    store.begin(`nudge:${i}`);
    store.update(i, { x: round(inst.x + move[0]), y: round(inst.y + move[1]) });
    ctx.onChange();
    clearTimeout(nudgeTimer);
    nudgeTimer = setTimeout(() => { store.commit(); ctx.onSettled(); }, 400);
  });
}

let nudgeTimer: ReturnType<typeof setTimeout>;
