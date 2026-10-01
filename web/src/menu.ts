/**
 * A menu: a temporary surface of actions, opened from a button.
 *
 * ⭐ Jerry, 2026-10-01: "I think the export and open should be a button, just
 * like save as, and ground plan." That is also what M3 says, from the other
 * direction — *use a menu to show a temporary set of actions; to show actions on
 * screen at all times, use a toolbar instead*. New, Save, Save As and Ground
 * plan are always available, so they stay buttons on the bar. Open and Export
 * are lists, so they are buttons that OPEN something.
 *
 * 🔴 WHAT THEY WERE: `<select>` elements whose change handler fired an action and
 * then did `sel.value = ""`. A control that clears itself after every use is not
 * holding a value — it was a menu wearing a select's clothes, and it dragged the
 * operating system's own chrome into a toolbar built from M3 tokens.
 *
 * ⭐ NO LIBRARY, because the browser grew the hard part. Checked on MDN
 * 2026-10-01:
 *
 *   Popover API              Baseline since April 2025
 *   CSS anchor positioning   Baseline since September 2026
 *
 * `popover` gives the top layer, light dismiss on an outside click, Escape, and
 * the invoker relationship — the things people used to install a floating-UI
 * package for.
 *
 * ⚠ ANCHOR POSITIONING IS ONE MONTH OLD as Baseline, so it is *newly* available
 * rather than widely, and `serve.py` opens the app in whatever browser the
 * designer defaults to. So the menu is positioned in script, which works
 * everywhere, and CSS anchoring is left as a later enhancement rather than a
 * dependency. See `docs/MENUS-AND-MATERIAL.md` §2.0b.
 */

export interface MenuItem {
  label: string;
  /** Material Symbols name, drawn leading. */
  icon?: string;
  /** Right-aligned, for a keyboard shortcut or a size. */
  trailing?: string;
  /** M3: an item that does not currently apply is DISABLED, not removed. */
  disabled?: boolean;
  /** A chosen option. Renders a tick and announces as a radio/checkbox item. */
  checked?: boolean;
  /** `radio` is one-of-a-set (a paper size); `check` is independent (rulers). */
  selection?: "radio" | "check";
  /** Opens beside this item, per M3. Submenus are a web feature. */
  submenu?: MenuGroup[];
  onSelect?: () => void;
}

export interface MenuGroup {
  /** Optional heading. On web M3 separates groups with a divider, not a gap. */
  heading?: string;
  items: MenuItem[];
}

/** ⚠ A STACK, not a single menu: a submenu is open ON TOP of its parent, and
 *  closing the parent has to take its children with it. */
let stack: HTMLElement[] = [];

function dismiss(el: HTMLElement): void {
  try { (el as unknown as { hidePopover(): void }).hidePopover(); } catch { /* already gone */ }
  el.remove();
}

/** Close everything. Safe to call when nothing is open. */
export function closeMenu(): void {
  for (const el of stack.slice().reverse()) dismiss(el);
  stack = [];
}

/** Close just the menus above `depth`, leaving the parent open. */
function closeAbove(depth: number): void {
  while (stack.length > depth) dismiss(stack.pop()!);
}

/** Does this browser have the Popover API? */
function hasPopover(el: HTMLElement): boolean {
  return typeof (el as unknown as { showPopover?: unknown }).showPopover === "function";
}

/**
 * Open `groups` anchored under `anchor`.
 *
 * ⚠ Rebuilt on every open rather than kept around. The plots list changes when a
 * file is saved, and a menu that caches its items is a menu that lies.
 */
export function openMenu(anchor: HTMLElement, groups: MenuGroup[]): void {
  closeMenu();
  build(anchor, groups, 0);
}

function build(anchor: HTMLElement, groups: MenuGroup[], depth: number): void {
  closeAbove(depth);

  const menu = document.createElement("div");
  menu.className = "menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("popover", "auto");

  groups.forEach((g, gi) => {
    // M3, Menus → Gaps & dividers: on web, use a divider. Gaps are not available.
    if (gi > 0) {
      const hr = document.createElement("div");
      hr.className = "menu-divider";
      menu.appendChild(hr);
    }
    if (g.heading) {
      const h = document.createElement("div");
      h.className = "menu-heading";
      h.textContent = g.heading;
      menu.appendChild(h);
    }
    for (const item of g.items) {
      const b = document.createElement("button");
      b.className = "menu-item";
      b.setAttribute("role", item.selection === "radio" ? "menuitemradio"
                           : item.selection === "check" ? "menuitemcheckbox" : "menuitem");
      if (item.selection) b.setAttribute("aria-checked", String(!!item.checked));
      if (item.submenu) b.setAttribute("aria-haspopup", "menu");
      b.type = "button";
      if (item.disabled) b.disabled = true;
      // ⚠ The tick occupies the SAME slot as a leading icon, so a list of
      // options does not jump sideways as the chosen one moves.
      if (item.selection) {
        const t = document.createElement("span");
        t.className = "material-symbols-outlined menu-tick";
        t.setAttribute("aria-hidden", "true");
        t.textContent = item.checked ? "check" : "";
        b.appendChild(t);
      }
      if (item.icon) {
        const i = document.createElement("span");
        i.className = "material-symbols-outlined";
        i.setAttribute("aria-hidden", "true");
        i.textContent = item.icon;
        b.appendChild(i);
      }
      const label = document.createElement("span");
      label.className = "menu-label";
      label.textContent = item.label;
      b.appendChild(label);
      if (item.trailing) {
        const t = document.createElement("span");
        t.className = "menu-trailing";
        t.textContent = item.trailing;
        b.appendChild(t);
      }
      if (item.submenu) {
        const chev = document.createElement("span");
        chev.className = "material-symbols-outlined menu-more";
        chev.setAttribute("aria-hidden", "true");
        chev.textContent = "chevron_right";
        b.appendChild(chev);
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          // ⚠ Opens BESIDE, and leaves the parent standing — M3: "Submenus
          // should open next to the parent menu item without overlapping it."
          build(b, item.submenu!, depth + 1);
        });
      } else {
        b.addEventListener("click", () => {
          closeMenu();
          item.onSelect?.();
        });
      }
      menu.appendChild(b);
    }
  });

  // 🔴 A SUBMENU IS APPENDED INSIDE ITS PARENT, not to <body>. Showing an `auto`
  // popover dismisses every other `auto` popover that is not NESTED inside it,
  // and nesting is established by DOM ancestry. Appending to <body> made the
  // browser treat the submenu as unrelated and close the parent — measured: the
  // Export menu collapsed to 0x0 the moment Sheet was clicked, which then took
  // the submenu's own anchor with it and placed it at the top-left corner.
  //
  // Being `position:fixed`, living inside the parent costs it nothing.
  const parent = depth > 0 ? stack[depth - 1] : undefined;
  (parent ?? document.body).appendChild(menu);
  stack.push(menu);

  if (hasPopover(menu)) {
    (menu as unknown as { showPopover(): void }).showPopover();
  } else {
    // ⚠ Older browsers: no top layer and no light dismiss, so both are provided.
    // The app still works; it just does not get them for free.
    menu.style.position = "fixed";
    menu.style.zIndex = "1000";
    setTimeout(() => {
      const away = (e: MouseEvent) => {
        if (!menu.contains(e.target as Node)) { closeMenu(); document.removeEventListener("pointerdown", away); }
      };
      document.addEventListener("pointerdown", away);
    }, 0);
  }

  place(menu, anchor, depth > 0);

  // ⚠ Escape closes even where popover's own handling is missing, and focus
  // returns to the button rather than being dropped on the document.
  menu.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    // ⚠ Escape in a SUBMENU closes only that one and returns to the item it came
    // from. Closing the whole stack would throw away a choice half made.
    if (depth > 0) { closeAbove(depth); anchor.focus(); }
    else { closeMenu(); anchor.focus(); }
  });
  menu.querySelector<HTMLButtonElement>(".menu-item:not(:disabled)")?.focus();
}

/**
 * Put the menu under its button, and keep it on screen.
 *
 * ⚠ In script, not in CSS. M3 says a menu that would be cut off should move
 * rather than be clipped, and anchor positioning does exactly that — but it is
 * one month into Baseline, so this does it by arithmetic and works everywhere.
 */
function place(menu: HTMLElement, anchor: HTMLElement, beside = false): void {
  const a = anchor.getBoundingClientRect();
  const m = menu.getBoundingClientRect();
  const pad = 8;
  // A submenu opens to the SIDE of its item; a top-level menu drops below its
  // button.
  let left = beside ? a.right + 2 : a.left;
  let top = beside ? a.top - 8 : a.bottom + 4;
  if (beside && left + m.width > window.innerWidth - pad) left = a.left - m.width - 2;
  // Off the right-hand edge: align the menu's right edge to the button's.
  if (left + m.width > window.innerWidth - pad) {
    left = Math.max(pad, a.right - m.width);
  }
  // No room below: flip above, which is the case a long plots list hits first.
  if (top + m.height > window.innerHeight - pad) {
    const above = a.top - m.height - 4;
    top = above >= pad ? above : Math.max(pad, window.innerHeight - m.height - pad);
  }
  // ⚠ Clamped. The arithmetic above can still produce a negative edge when the
  // anchor is near a corner, and a menu that starts off-screen cannot be read
  // back onto it.
  menu.style.position = "fixed";
  menu.style.left = `${Math.round(Math.max(pad, left))}px`;
  menu.style.top = `${Math.round(Math.max(pad, top))}px`;
  menu.style.margin = "0";
}
