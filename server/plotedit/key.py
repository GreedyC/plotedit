"""The legend / instrument key — RP-2 §5.

    §5.0: "Placement is acceptable in any location that does not conflict with
    other information."

⭐ A key is not a parts list. It is the drawing's own dictionary: it says what
each shape means, so a stranger can read the plot without asking the designer.
That is why §5.1 asks for the SYMBOLS themselves and not just names, and why
they are drawn at the plot's own scale here — a key drawn at a different size
teaches the reader a shape they will not see again.

§5.1 wants, and this produces:
  · symbols of every luminaire and device on the plot, with descriptions
  · beam spread where the name does not already carry it
  · every notation used, explained
  · colour manufacturer designations (R = Rosco, L = Lee, G = Gam …)
  · template manufacturer designation, when there is one
  · wattage and/or ANSI lamp code
  · symbols for any accessories

⚠ It reports what is ON THE PLOT, never the whole fixture table. A key listing
instruments nobody hung is a key nobody finishes reading.
"""
from collections import Counter
from typing import Any, Dict, List

from . import photometrics as ph
from . import symbols as sym
from .scaled_pdf import ft

# §5.1: "Color manufacturer designation (e.g., R = Rosco, L = Lee, G = Gam)".
COLOR_MAKERS = {"R": "Rosco", "L": "Lee", "G": "Gam", "A": "Apollo", "AP": "Apollo"}


def colors_used(plot: Dict[str, Any]) -> List[str]:
    """Every gel on the plot, in order of first appearance."""
    seen, out = set(), []
    for i in plot.get("instruments", []):
        c = (i.get("color") or "").strip()
        if c and c.upper() not in seen:
            seen.add(c.upper()); out.append(c)
    return out


def makers_used(plot: Dict[str, Any]) -> List[str]:
    """Which manufacturers' prefixes actually appear, expanded.

    Only the ones used: a key that explains L = Lee on a plot with no Lee in it
    is teaching the reader something they do not need.
    """
    found = []
    for c in colors_used(plot):
        for part in c.replace("/", "+").split("+"):
            part = part.strip().upper()
            for n in (2, 1):
                if part[:n] in COLOR_MAKERS and COLOR_MAKERS[part[:n]] not in found:
                    found.append(COLOR_MAKERS[part[:n]]); break
    return found


def _natural(name: str):
    """Sort key that reads numbers as numbers: S4 19 before S4 26 before S4 36.

    Plain alphabetical puts "S4 19" after "S4 136", which is the sort order of a
    filing cabinet rather than of a lens rack.
    """
    import re as _re
    return [int(t) if t.isdigit() else t.lower()
            for t in _re.split(r"(\d+)", name or "")]


def types_used(plot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One row per fixture type on the plot: symbol, description, watts, count.

    Ordered BY FIXTURE, smallest lens first — the order Jerry wrote them in
    2026.09.23 ("1) S4 19, 3) S4 26, 2) S4 36"). A key is read by someone
    looking for a shape they can see on the plot, so it should be ordered the
    way they would look: by instrument, not by how many there happen to be.
    """
    counts = Counter((i.get("type") or "").strip()
                     for i in plot.get("instruments", []) if i.get("type"))
    rows = []
    for name in sorted(counts, key=_natural):
        n = counts[name]
        key, row, note = ph.lookup(name)
        # §5.1 asks for beam spread "if the numeric value is not part of the
        # luminaire's name". It is worth giving even when it looks like it is:
        # "S4 26" names the NOMINAL barrel, and the measured field is 25° with a
        # beam of 18°. The nominal number is the product; these are the light.
        # Repeating a name would be clutter — publishing the real angles is not.
        field = row.get("field") if row else None
        beam = row.get("beam") if row else None
        watts, wnote = ph.watts_for(name) if row else (None, "")
        rows.append({"name": name, "key": key, "count": n,
                     "field": field, "beam": beam,
                     "watts": watts, "watt_note": wnote,
                     "unknown": row is None, "note": note})
    return rows


def accessories_used(plot: Dict[str, Any]) -> List[str]:
    seen, out = set(), []
    for i in plot.get("instruments", []):
        for a in i.get("accessories") or []:
            if str(a).lower() not in seen:
                seen.add(str(a).lower()); out.append(str(a))
    return out


def shaded_used(plot: Dict[str, Any]) -> bool:
    """Does any instrument on this plot carry the shaded-rear mark?"""
    from .scaled_pdf import _shade_rear_for
    return any(_shade_rear_for(i.get("type"), i.get("lamp"))
               for i in plot.get("instruments", []))


def draw(sheet, plot, x, y, width=11.0, line=0.85, title="INSTRUMENT KEY"):
    """Draw the key at (x, y) — its TOP-left corner — in plot feet.

    Symbols are drawn at the sheet's own scale. A key drawn at some other size
    teaches the reader a shape they will never see again.

    Returns the y it finished at, so a caller can stack a schedule under it.
    """
    from reportlab.lib.colors import grey
    sheet.layer("NOTES")
    cy = y
    sheet.text(x, cy, title, size=8, bold=True)
    cy -= line * 1.2

    # ── the luminaires themselves ──────────────────────────────────────────
    for r in types_used(plot):
        prims = sym.for_type(r["name"])
        # ⚠ Space each row by the SYMBOL's own size, and lay the instruments
        # horizontally. Drawn nose-up on a fixed row height they overlapped each
        # other — a key whose symbols collide teaches the reader the wrong shape,
        # which is worse than no key.
        rad = sym.radius(prims)
        cy -= rad                                  # drop to this row's centre
        sym.draw(sheet, prims, x + 0.9, cy, rotate_deg=90, width=1.0)
        # Jerry's own notation, 2026.09.23: "1) S4 19, 3) S4 26, 2) S4 36."
        desc = f"{r['count']}) {r['name']}"
        sheet.text(x + 2.2, cy - line * 0.1, desc, size=6, bold=True)
        # ⚠ No beam, field or wattage here — Jerry, 2026.09.23: "we can lose the
        # wattage too, that will be on the instrument schedule."
        #
        # The angles agree with §5.1, which asks for beam spread only "if the
        # numeric value is not part of the luminaire's name" — "S4 26" carries
        # it. **The wattage is a deliberate DEPARTURE**: §5.1 asks for "wattage
        # (total luminaire load) and/or ANSI lamp code". It is dropped because it
        # is on the instrument schedule, and a key that repeats the schedule is a
        # second place for the same fact to go stale.
        #
        # All of it stays in the data model for anything that computes. A key is
        # for reading shapes.
        bits = []
        if r["unknown"]:
            # ⚠ Never silently. A type the tool cannot identify is a type the
            # reader should be told about, not one quietly given no angle.
            bits.append("NOT IN THE FIXTURE TABLE — angles and load unknown")
        if bits:
            sheet.text(x + 2.2, cy - line * 0.75, " · ".join(bits), size=5.5, color=grey)
        cy -= rad + line * 0.15

    # ── §5.1: every notation used, explained ───────────────────────────────
    control = plot.get("control", "dimmer-per-circuit")
    cy -= line * 0.4
    sheet.text(x, cy, "NOTATION", size=7, bold=True)
    cy -= line
    rows = [("hexagon", "circuit & dimmer" if control == "dimmer-per-circuit" else "circuit"),
            ("circle", "channel"),
            ("number in the body", "unit number")]
    if control == "hard-and-soft-patch":
        rows.insert(1, ("rectangle", "dimmer"))

    # ⭐ SAY IT ON THE SHEET WHEN THE PLOT USES IT. On a plot with addressed
    # units the hexagon carries the address and the rectangle the circuit, which
    # reads backwards to anyone who knows the RP-2 plates — so a reader who has
    # not been told will read a rectangle as a dimmer. Explained only when there
    # is something to explain; a legend line for notation nobody used is clutter.
    _addressed = [i for i in plot.get("instruments", [])
                  if str(i.get("address") or "").strip()
                  and not str(i.get("dimmer") or "").strip()]
    if _addressed:
        rows[0] = ("hexagon", "dimmer — or the DMX ADDRESS, which always carries "
                              "its universe (1/45)")
        rows.insert(1, ("rectangle", "circuit, where a unit is addressed rather "
                                     "than dimmed"))
    # ⭐ §6.15's shaded rear means "arc source"; Jerry uses it for a 750W lamp.
    # ONE MARK, TWO MEANINGS — so the key must say which, and only when the plot
    # actually uses it. A shaded symbol nobody explained is read as the other
    # thing.
    if shaded_used(plot):
        rows.append(("blackened back of the body", "750W lamp (§6.15's arc-source "
                                                   "mark, used here for the lamp)"))
    for shape, means in rows:
        sheet.text(x + 0.4, cy, f"{shape} = {means}", size=5.5)
        cy -= line * 0.72
    if control == "dimmer-per-circuit":
        sheet.text(x + 0.4, cy, "This house is DIMMER PER CIRCUIT — circuit and "
                                "dimmer are one number.", size=5.5, color=grey)
        cy -= line * 0.72

    # ── §5.1: colour, and the manufacturer designations actually used ──────
    cols = colors_used(plot)
    if cols:
        cy -= line * 0.4
        sheet.text(x, cy, "COLOR", size=7, bold=True)
        cy -= line
        for c in cols:
            factor, note = ph.gel_factor(c)
            txt = c + (f"  —  {factor * 100:.0f}% transmission" if factor else "")
            if "SPLIT" in (note or "").upper():
                txt += "  (SPLIT FRAME — no single figure describes the pool)"
            sheet.text(x + 0.4, cy, txt, size=5.5)
            cy -= line * 0.72
        makers = makers_used(plot)
        if makers:
            pref = ", ".join(f"{k} = {v}" for k, v in COLOR_MAKERS.items() if v in makers)
            sheet.text(x + 0.4, cy, pref, size=5.5, color=grey)
            cy -= line * 0.72
        sheet.text(x + 0.4, cy, "+ stacks (transmissions multiply) · / is a split frame",
                   size=5.5, color=grey)
        cy -= line * 0.72

    # ── §5.1: accessories, with their symbols ──────────────────────────────
    acc = accessories_used(plot)
    if acc:
        cy -= line * 0.4
        sheet.text(x, cy, "ACCESSORIES", size=7, bold=True)
        cy -= line * 1.1
        ax = x + 0.7
        for a in acc:
            where, k, _ = sym.resolve_accessory(a)
            if where == "front":
                shape = (sym.barn_door(2) if k == "bd2" else sym.barn_door(4)
                         if k == "bd4" else sym.top_hat(half=(k == "halfhat")))
                sym.draw(sheet, shape, ax, cy, rotate_deg=180, width=1.0)
            elif where == "gate":
                sheet.circle(ax, cy, 0.09, fill=None if k == "iris" else sym._black())
            sheet.text(ax + 0.55, cy - 0.06, a, size=5.5)
            ax += max(3.0, width / max(len(acc), 1))
        cy -= line * 1.3

    return cy
