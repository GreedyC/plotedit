/** The eight layers, in one place, because there were already two schemes.
 *
 * Before this file the app had layers twice and they did not agree: four fixed
 * toggles on screen (`plan`, `pools`, `focus`, `labels`) and six names in the
 * DXF (`BASE`, `POSITIONS`, `UNITS`, `TEXT`, `DIMS`, `NOTES`). Only two
 * concepts appeared in both, under different names. `pools` and `focus` could
 * be switched off on screen and were never written to the DXF at all;
 * `POSITIONS` and `UNITS` were separable in CAD and could not be hidden on
 * screen. See docs/LAYERS.md §0.
 *
 * ⭐ Jerry, 2026-10-01: "Can we merge the screen and DXF layer together, and
 * then store them in the JSON file? … Eventually we would give the user the
 * ability to add layers." So: one set, in the file, and a shape that a
 * user-added layer can join without a second system.
 *
 * 🔴 THE LIST HERE IS THE ONLY LIST. The chips in index.html are markup, which
 * means they are a second copy — exactly how the lamp dropdown drifted a whole
 * release behind LAMP_MF, twice. `layers.test.ts` reads the markup and requires
 * it to match this file, so the two cannot part company silently.
 */
import type { Plot } from "./plot.js";

export type LayerId =
  | "base" | "pools" | "positions" | "focus" | "units" | "labels"
  | "dimensions" | "notes";

export interface LayerDef {
  id: LayerId;
  /** What the chip says, and what the layer is called anywhere it is named. */
  label: string;
  /** The chip's tooltip. Every control in this toolbar has one — see #56. */
  title: string;
  /** Whether it has anything to draw ON SCREEN yet.
   *
   * ⚠ `dimensions` and `notes` are false: the rulers and the key exist only in
   * the exported PDF. They are still real layers carried in the file, so the
   * export can read one set rather than growing its own flags, but they get no
   * chip until there is something on screen for a chip to change. A control
   * that does nothing is worse than a missing one. */
  onScreen: boolean;
  /** What a plot that does not mention this layer means.
   *
   * 🔴 NOT "all true". `dimensions` defaults OFF because the rulers checkbox it
   * replaces was unchecked, and defaulting it on would have added rulers to
   * every PDF anyone exported from an existing plot. `notes` defaults ON
   * because the key block prints today with no way to stop it. The migration
   * has to preserve what each one did, not pick a tidy rule. */
  byDefault: boolean;
}

/** ⭐ ARRAY ORDER IS DRAW ORDER, bottom to top, and it is why pools sit under
 *  the pipes and labels on top of everything. The plan calls for the reader to
 *  reorder layers eventually (docs/LAYERS.md §6 step 4); when that lands it
 *  moves elements of the file's array, and this stays the seed order.
 *
 *  ⚠ The room rectangle and its grid are NOT a layer. They are the drawing's
 *  frame of reference — a plot with the room switched off is a set of
 *  coordinates with nothing to measure against. */
export const LAYERS: readonly LayerDef[] = [
  { id: "base", label: "plan", onScreen: true, byDefault: true,
    title: "Draw the imported ground plan under the plot" },
  { id: "pools", label: "pools", onScreen: true, byDefault: true,
    title: "Draw each light's pool where it lands" },
  { id: "positions", label: "positions", onScreen: true, byDefault: true,
    title: "Draw the pipes, booms and their mounts" },
  { id: "focus", label: "focus", onScreen: true, byDefault: true,
    title: "Draw the focus point and its leader line" },
  { id: "units", label: "units", onScreen: true, byDefault: true,
    title: "Draw the instrument symbols. Switch off to read the pipes alone" },
  { id: "labels", label: "labels", onScreen: true, byDefault: true,
    title: "Draw unit numbers, channels, colour and type" },
  { id: "dimensions", label: "dimensions", onScreen: false, byDefault: false,
    title: "Rulers and dimension strings. Printed, not drawn on screen" },
  { id: "notes", label: "notes", onScreen: false, byDefault: true,
    title: "The key and the notes block. Printed, not drawn on screen" },
];

/** The layers with something to draw on screen, which is what gets a chip. */
export const SCREEN_LAYERS: readonly LayerDef[] =
  LAYERS.filter(l => l.onScreen);

/** One layer as the plot file carries it.
 *
 * ⚠ NO LABEL for a built-in. The label lives in `LAYERS` above, so renaming a
 * chip is a code change and not a migration — and a file cannot end up
 * disagreeing with the program about what a layer is called. A user-added layer
 * will need its `name` here, because nothing in the code knows it.
 */
export interface PlotLayer {
  id: string;
  visible: boolean;
  /** User-added layers only; built-ins take their label from `LAYERS`. */
  name?: string;
}

export type Visibility = Record<LayerId, boolean>;

/** What a new plot is seeded with: all eight, in draw order, at their defaults. */
export function defaultLayers(): PlotLayer[] {
  return LAYERS.map(l => ({ id: l.id, visible: l.byDefault }));
}

/**
 * Which layers are visible in this plot — the migration, in one function.
 *
 * 🔴 A PLOT SAVED BEFORE TODAY HAS NO `layers` AT ALL, and the rule has to be
 * written down or it gets guessed differently in each caller: **a layer the
 * file does not mention takes its default**, never "invisible". Read it the
 * other way and every plot drawn before this release opens as an empty room,
 * which is the single worst thing this change could do.
 *
 * ⚠ It is per-layer, not all-or-nothing, so a file written by a LATER version
 * that adds a ninth layer still opens correctly here: the eight it knows are
 * read from the file and anything else is ignored.
 */
export function visibilityOf(plot: Plot): Visibility {
  const out = {} as Visibility;
  const inFile = new Map(
    (plot.layers ?? []).map(l => [l.id, l.visible] as const));
  for (const l of LAYERS) {
    const v = inFile.get(l.id);
    out[l.id] = typeof v === "boolean" ? v : l.byDefault;
  }
  return out;
}

/** Everything on, for the paperwork.
 *
 * 🔴 THE RULE, from docs/LAYERS.md: layer visibility is a property of the
 * DRAWING. The schedule, the hookup, the channel count and the circuit loads
 * always report the whole rig. A load computed without the units somebody
 * switched off is the failure that trips a breaker on a Thursday, so the
 * paperwork asks for this and never for `visibilityOf`.
 */
export function allVisible(): Visibility {
  const out = {} as Visibility;
  for (const l of LAYERS) out[l.id] = true;
  return out;
}
