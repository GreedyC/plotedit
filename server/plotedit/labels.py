#!/usr/bin/env python3
"""Where a position's NAME goes, so it does not land on something else.

⭐ RP-2 §2.1 wants every hanging position identified; it does not say where the
name goes, because on a drawing that is a fitting problem, not a standard. The
name went at the pipe's stage-left end, always, and on the Bluver plot that put
`CAT 1  (FOH)` and `HOUSE LEFT BOX BOOM 1` on top of each other and both across
the box boom's symbol — three pieces of ink in one place, and the one an
electrician needs first is the one underneath.

⚠ THE RULE LIVES HERE ONCE. The paper places labels through plot_to_pdf; the
browser asks POST /labels. The two must choose the same slot or the same plot
reads differently on screen and on paper — which has happened three times in a
week with other marks.

⚠ Text WIDTH is each side's own business. ReportLab measures Helvetica and the
browser measures whatever the system gives it, so the caller supplies the box
and this module only chooses between candidate slots. The decision is shared;
the metrics cannot be.
"""

# How much clear air a label wants around it, in feet.
PAD = 0.25


def _box(x, y, w, h, align):
    """A label's footprint from its anchor. `align` says which end is anchored."""
    if align == "right":
        x0 = x - w
    elif align == "center":
        x0 = x - w / 2.0
    else:
        x0 = x
    # The anchor is the BASELINE, so the glyphs stand above it.
    return (x0, y - h * 0.25, x0 + w, y + h * 0.75)


def _overlap(a, b):
    """Area shared by two boxes. Zero when they are clear of each other."""
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def _grow(b, pad):
    return (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)


def disc(x, y, r):
    """An obstacle box around something round — a symbol, a boom stack."""
    return (x - r, y - r, x + r, y + r)


def candidates(pos, w, h, gap=0.5):
    """Where this position's label could go, best first.

    Horizontal positions: at either END of the pipe, above it or below it, then
    outboard beyond the end. A position's name belongs near its own pipe, so
    every candidate stays on it — none of them wander into the room.

    Vertical positions (booms) are a point, so the name goes beside it, and
    `outboard` decides which side.
    """
    x1, y1 = pos["x1"], pos["y1"]
    x2, y2 = pos.get("x2", x1), pos.get("y2", y1)
    half = pos.get("half", 0.0)
    if pos.get("vertical"):
        out = pos.get("outboard", -1)
        side = 1 if out > 0 else -1
        near = x1 + side * (half + gap)
        return [
            (near, y1 - h * 0.35, "left" if side > 0 else "right"),
            (x1, y1 + half + gap + h * 0.5, "center"),
            (x1, y1 - half - gap - h * 0.5, "center"),
            (x1 - side * (half + gap), y1 - h * 0.35, "right" if side > 0 else "left"),
        ]
    top = max(y1, y2) + half + gap
    bot = min(y1, y2) - half - gap - h * 0.5
    lo, hi = min(x1, x2), max(x1, x2)
    return [
        (lo, top, "left"),
        (hi, top, "right"),
        (lo, bot, "left"),
        (hi, bot, "right"),
        (lo - gap, (y1 + y2) / 2.0 - h * 0.35, "right"),
        (hi + gap, (y1 + y2) / 2.0 - h * 0.35, "left"),
    ]


# A candidate that runs off the SHEET is not a candidate. Weighted far above a
# simple overlap so a clear-but-clipped slot never beats a crowded-but-visible
# one: an overlap is untidy, a clipped label is a position with no name at all.
OFF_SHEET = 1000.0


def _outside(box, bounds):
    """How much of a box falls outside the drawable area, in square feet."""
    if not bounds:
        return 0.0
    x0, y0, x1, y1 = bounds
    area = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    dx = min(box[2], x1) - max(box[0], x0)
    dy = min(box[3], y1) - max(box[1], y0)
    inside = dx * dy if dx > 0 and dy > 0 else 0.0
    return max(0.0, area - inside)


def place(items, obstacles=(), pad=PAD, bounds=None):
    """Choose a slot for each label. Returns one (x, y, align) per item.

    Greedy and in the order given, because that is what a drafter does: put the
    first name down, then fit the next around it. A label that fits nowhere
    takes the LEAST crowded slot rather than its first choice — the drawing is
    better with an overlap the eye can untangle than with three labels stacked.

    ⚠ Nothing is ever dropped. A position whose name will not fit anywhere is
    still a position, and a plot that silently omits one is worse than a plot
    with a label sitting close to a symbol.
    """
    taken = []
    out = []
    for it in items:
        best, best_score = None, None
        for (x, y, align) in it["candidates"]:
            raw = _box(x, y, it["w"], it["h"], align)
            b = _grow(raw, pad)
            score = sum(_overlap(b, o) for o in obstacles) \
                + sum(_overlap(b, t) for t in taken) \
                + _outside(raw, bounds) * OFF_SHEET
            if score == 0:
                best, best_score = (x, y, align), 0.0
                break
            if best_score is None or score < best_score:
                best, best_score = (x, y, align), score
        x, y, align = best
        taken.append(_box(x, y, it["w"], it["h"], align))
        out.append({"x": x, "y": y, "align": align, "overlap": round(best_score, 4)})
    return out


def text_for(pos, system=None):
    """The string a position's label actually shows, CAPS and all.

    ⚠ Built here so the paper and the screen show the SAME name. The trim
    suffix and the (FOH) suffix used to be assembled in two places, which is one
    rename away from the two drawings disagreeing about what a pipe is called.

    Trim appears only on a position that can MOVE — RP-2 §2.1 asks for "trim
    measurements for MOVABLE mounting positions", and a number that cannot
    change is clutter on every dead-hung pipe in the room.
    """
    from . import photometrics as _ph
    name = (pos.get("name") or "").strip()
    text = name
    if pos.get("trim") is not None and pos.get("movable"):
        text += f" — trim {_ph.fmt_ft(pos['trim'], system)}"
    foh = pos.get("foh")
    if foh is None:
        foh = (pos.get("type") or "").strip().lower() == "catwalk"
    if foh and "FOH" not in name.upper():
        text += "  (FOH)"
    # ⚠ Position names are drawn in CAPS, but a unit SYMBOL is not a word. In SI
    # "m" is metres and "M" is the mega- prefix, so uppercasing the whole string
    # turned a 4.27 m trim into "4.27 M" — wrong, and wrong in a way a metric
    # reader notices immediately. Feet and inches survive it; metres do not.
    import re as _re
    return _re.sub(r"(\d)\s*M\b", r"\1 m", text.upper())


def plan(positions, instruments, measure, room_width=None, unit_r=1.35,
         system=None,
         text_h=0.4, gap=0.5, bounds=None):
    """Fit every position name around the units and around each other.

    `measure(text) -> width in feet` belongs to the caller: ReportLab knows
    Helvetica, the browser knows whatever the system gave it. The SLOT is chosen
    here so both drawings pick the same one.

    ⚠ `bounds` is the drawable area, (x0, y0, x1, y1) in plot feet. Pass it. The
    first version did not, moved CAT 1's name to the stage-right end to get it
    off the box boom, and put it 22 feet off the edge of the sheet — trading a
    collision for a position with no name on the drawing at all.

    Returns one record per position, in the order given:
        {"name", "text", "x", "y", "align", "overlap"}
    """
    from . import positions as _P
    from . import symbols as _sym

    boom_names = {(p.get("name") or "").strip().lower()
                  for p in positions if _P.is_vertical(p)}

    # ⚠ The obstacles are the symbols an electrician reads, not their notation.
    # Treating the whole channel-and-circuit stack as solid leaves a plot with
    # nowhere to put a name, and the placement then degrades to "least bad"
    # everywhere.
    obstacles = []
    for i in instruments:
        if (i.get("position") or "").strip().lower() in boom_names:
            continue        # drawn in its boom's elevation, not here
        obstacles.append(disc(i.get("x", 0.0), i.get("y", 0.0), unit_r))
    for p in positions:
        if _P.is_vertical(p):
            # The hatched stack standing for the boom's units.
            obstacles.append(disc(p["x1"], p["y1"], unit_r))

    # ⚠ And the §6.12 ELEVATIONS, which occupy the margin off the stage-left
    # edge. Without them a long name pushed outboard runs straight through a
    # boom's pipe — the margin looks empty only if you forget what is drawn in
    # it, which is precisely the mistake the elevations were added to fix.
    from . import booms as _b
    for e in _b.layout(positions, instruments):
        obstacles.append((e["x"] - 1.2, e["y"] - 1.6,
                          e["x"] + e["unit_gap"] + 2.6, e["y"] + e["top"] + 1.0))

    items, meta = [], []
    for p in positions:
        text = text_for(p)
        vertical = _P.is_vertical(p)
        kind = (p.get("type") or "electric").strip().lower()
        if vertical:
            # ⚠ Clear the boom's OWN stack symbol, not just its mount. Measured
            # from the symbol, because a label that starts 1'-2" from a point
            # with a 1'-1" symbol on it is a label on the symbol.
            half = max((p.get("width") or 1.4) / 2.0,
                       _sym.radius(_sym.for_type("")) if False else unit_r)
            out = -1 if room_width is None else (1 if p["x1"] >= room_width / 2.0 else -1)
            spec = {"x1": p["x1"], "y1": p["y1"], "vertical": True,
                    "half": half, "outboard": out}
        else:
            half = (p.get("width") or (3.0 if kind == "catwalk"
                                       else 1.5 if kind == "truss" else 0.0)) / 2.0
            spec = {"x1": p["x1"], "y1": p["y1"],
                    "x2": p.get("x2", p["x1"]), "y2": p.get("y2", p["y1"]),
                    "half": half}
        w = measure(text)
        items.append({"candidates": candidates(spec, w, text_h, gap),
                      "w": w, "h": text_h})
        meta.append((p.get("name"), text))

    out = []
    for (name, text), spot in zip(meta, place(items, obstacles, bounds=bounds)):
        spot = dict(spot)
        spot["name"] = name
        spot["text"] = text
        out.append(spot)
    return out


# ----------------------------------------------------- colour labels that touch

# ⚠ An average glyph is about .62 of the cap height in the sans face both the
# sheet and the browser use. Measuring properly would mean a font metric in two
# languages; this is deliberately a slight OVER-estimate, because staggering a
# label that would just have cleared costs nothing and letting two run together
# costs a misread gel at the focus call.
CHAR_W = 0.62

# ⭐ MEASURED, not guessed. In the browser the colour label is drawn at
# font-size 0.5 (user units are feet) and "R52+R119" measures 2.52 ft across —
# eight characters, so .63 of the font size each. CHAR_W above is that number.
#
# ⚠ The two renderers size this label DIFFERENTLY and both are right. On screen
# it is 0.5 FEET tall, so it scales with the drawing and covers the same stage
# area at every zoom. On paper it is 7 POINTS tall, so in feet it shrinks as the
# scale grows: 0.39 ft at 1/4" = 1'-0", 0.19 ft at 1/2". That is why the height
# is an argument here and not a constant — the same pipe collides on screen and
# may be perfectly clear in print at 1/4".

# Space to leave between two labels. ⚠ Not touching is not enough: two colour
# strings a hair apart still read as one at arm's length under work light.
PAD_FT = 0.35


def color_width(text, text_h_ft, char_w=CHAR_W):
    """Roughly how wide a colour label is, in FEET at the current scale."""
    return len(str(text or "")) * char_w * text_h_ft


def color_tiers(instruments, text_h_ft, char_w=CHAR_W, pad=PAD_FT):
    """How far out each unit's colour label has to sit so they do not touch.

    Returns one tier per instrument, index-aligned: 0 is the normal distance,
    1 is a step further out along the same axis, and so on.

    🔴 THE BUG THIS EXISTS FOR. On the demo plot, GRID C units 3 and 4 sit 2'-6"
    apart where the rest of the pipe is at 5'-6", and "R52+R119" is wider than
    the gap. The two labels rendered as "R52+R119R52+R119" with nothing between
    them — in a column an electrician reads under work light while holding a gel
    frame. Both units happened to be the SAME colour, which hid how bad it is:
    two different colours run together give the reader no way to tell where one
    ends. (Issue #21.)

    ⭐ FURTHER OUT, NOT UP OR DOWN. RP-2 §6.14.2 puts colour in front of the
    unit, across the lens. Moving a label above or below the symbol to dodge a
    neighbour would put it where the standard says something else lives. Stepping
    further along the SAME axis keeps the meaning and only changes the distance,
    which is what a drafter does by hand.

    ⚠ Scale-aware, which is why the text height is an argument rather than a
    constant. Labels are drawn at a fixed point size, so at 1/2" scale they cover
    half as much of the STAGE as at 1/4" and the same pipe may not collide at
    all. A rule that ignored that would stagger plots which were already fine.
    """
    tiers = [0] * len(instruments)

    # Neighbours on the same hanging position are the ones that collide; two
    # units on different pipes are already a pipe apart.
    groups = {}
    for i, inst in enumerate(instruments):
        if not (inst.get("color") or "").strip():
            continue
        groups.setdefault(inst.get("position") or "", []).append(i)

    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        # Sort along whichever axis the position actually runs. A boom's units
        # share an x and differ in y; a batten is the other way round.
        xs = [float(instruments[i].get("x") or 0) for i in idxs]
        ys = [float(instruments[i].get("y") or 0) for i in idxs]
        along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        pos_of = (lambda i: float(instruments[i].get("x") or 0)) if along_x \
            else (lambda i: float(instruments[i].get("y") or 0))
        idxs = sorted(idxs, key=pos_of)

        # The right-hand edge already claimed at each tier.
        claimed = []
        for i in idxs:
            w = color_width(instruments[i].get("color"), text_h_ft, char_w)
            here = pos_of(i)
            left, right = here - w / 2.0 - pad / 2.0, here + w / 2.0 + pad / 2.0
            tier = 0
            while tier < len(claimed) and claimed[tier] > left:
                tier += 1
            if tier == len(claimed):
                claimed.append(right)
            else:
                claimed[tier] = right
            tiers[i] = tier
    return tiers
