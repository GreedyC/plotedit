/**
 * One place that makes a button, so every button has an emphasis.
 *
 * ⭐ Jerry, 2026-10-01, on the toolbars: "the look and feel and order are
 * probably the weakest part of the app." The buttons built in TypeScript were
 * part of that — but NOT in the way the plan first claimed.
 *
 * ⚠ THEY WERE NEVER UNSTYLED. The global `button` rule in index.html reaches
 * them, so a class-less button is Roboto, `--primary` green, pill radius,
 * transparent — an M3 **text** button, which is a real variant. Measured in the
 * app before writing this, because the first draft of
 * `docs/MENUS-AND-MATERIAL.md` said they rendered in browser chrome and that was
 * wrong.
 *
 * 🔴 What was actually wrong: EVERY ONE OF THEM WAS THE SAME EMPHASIS. In a
 * position row, `+ unit`, `draw`, `renumber`, `number by clicking` and `delete`
 * all looked alike, so nothing said which is the ordinary thing to do and which
 * is the one you rarely want. M3 publishes five emphases for exactly this, and
 * `index.html` already defines filled, tonal, outlined and danger — nobody was
 * applying them.
 *
 * So the fix is not a stylesheet, it is making the emphasis impossible to omit:
 * `variant` is a required argument.
 */

/** M3's emphasis ladder, in the order M3 lists it. `text` is the quietest. */
export type Variant = "filled" | "tonal" | "outlined" | "text" | "danger";

export interface ButtonSpec {
  /** Sentence case, one to three words — M3's rule for label text. */
  label: string;
  variant: Variant;
  /** A Material Symbols name. M3 wants an icon that matches the action. */
  icon?: string;
  /** The tooltip. ⚠ M3: a plain tooltip is NOT needed when the element already
   *  has label text, so this is for the extra sentence, not a repeat of it. */
  title?: string;
  /** `small` is the dense size used inside the side panels. */
  dense?: boolean;
  onClick?: (e: MouseEvent) => void;
}

export function button(spec: ButtonSpec): HTMLButtonElement {
  const b = document.createElement("button");
  // ⚠ `text` is the default look, so it adds no class — but it still has to be
  // ASKED FOR. A variant nobody typed is how the panel ended up with five
  // identical buttons.
  const classes = [spec.variant === "text" ? "" : spec.variant,
                   spec.dense ? "small" : ""].filter(Boolean);
  if (classes.length) b.className = classes.join(" ");
  if (spec.icon) {
    const i = document.createElement("span");
    i.className = "material-symbols-outlined";
    i.textContent = spec.icon;
    // ⚠ The glyph is decoration beside a label a screen reader already reads.
    i.setAttribute("aria-hidden", "true");
    b.appendChild(i);
  }
  b.appendChild(document.createTextNode(spec.label));
  if (spec.title) b.title = spec.title;
  if (spec.onClick) b.addEventListener("click", spec.onClick);
  return b;
}
