#!/usr/bin/env python3
"""Instrument symbols drawn to USITT RP-2 (2006).

The standard is in docs/reference/USITT-RP-2-2006.pdf; the plates are pages 4–9,
and docs/SYMBOLS.md maps each fixture family to its section. **Read those before
changing anything here.** The previous symbols were drawn from memory and were
wrong in most respects; these are traced from the plates.

COORDINATES. Every symbol is defined in a local frame:

    +a  is toward the BACK of the instrument (the reflector end)
    -a  is toward the FRONT (the lens, where the light goes)
    +c / -c are the two sides
    the ORIGIN is the yoke — the hanging point, which is where RP-2 §2.2 says
    the symbol must be positioned

Sizes are in FEET and approximate the real instrument, per §2.2: "luminaire
symbols ... should represent the approximate size and shape of the luminaires in
scale." A Source Four is about 22" long and 7" across the body.

Each builder returns a list of (kind, payload) primitives so the same definition
can be drawn to PDF, to SVG, or to DXF without three copies of the geometry:

    ("poly",  [(a, c), ...], closed)      an outline
    ("line",  (a1, c1), (a2, c2))         a single stroke
    ("circle", (a, c), r, filled)
    ("text",  (a, c), "T", size)          a letter inside the symbol
"""
import math

# ------------------------------------------------------------------ helpers

def _mirror(pts):
    """Given the upper half of a symmetrical outline, return the whole thing."""
    return list(pts) + [(a, -c) for a, c in reversed(pts)]


# ------------------------------------------------------- §6.1.6 Enhanced ERS

# The Source Four family. RP-2 codes the beam angle by the MARK INSIDE THE LENS
# HOUSING, not by the length of the barrel:
#
#   70°        stepped rings at the front
#   50°        a wedge pointing back into the body
#   36°–40°    no mark
#   26°–30°    one diagonal
#   19°–20°    an X
#
# Only the very narrow units (15°, 10°, 5°) get a longer body, and those are a
# different sub-family in §6.1.6.

ERS_MARKS = {
    90: "rings", 70: "rings", 50: "wedge", 40: None, 36: None,
    30: "diagonal", 26: "diagonal", 20: "cross", 19: "cross",
    15: "long", 14: "long", 10: "long", 5: "long",
}


def enhanced_ers(angle=26, length=1.667, width=0.625):
    """§6.1.6. Defaults are a Source Four: 20" long, 7.5" across the body.

    Shape grammar traced from the plate. Reading from the FRONT backwards:

        0.00 - 0.26 L   lens housing — a SHORT, STEEP flare to a flat front face
        0.26 - 0.34 L   the neck, at 62% of the body width
        0.34 - 1.00 L   the body, at full width, tapered at the back

    The flare is short and steep in RP-2, not a long gentle cone. Getting that
    wrong is what made the second attempt read as a funnel rather than an ERS.

    The front face is a touch TALLER than the body — that flare is what makes an
    ERS read as an ERS, and getting it backwards was the first attempt's worst error.

    ⚠ RP-2 draws the symbol at about 2:1; a real Source Four is nearer 2.7:1.
    §2.2 asks for approximate real size and shape, so the REAL footprint is used
    and RP-2's shape grammar is stretched along it. The silhouette reads the same
    and the plot does not under-state how much pipe a unit occupies.
    """
    w = width / 2
    front = -length * 0.60          # yoke sits 40% back from the front
    back = length + front
    face = front
    flare_end = front + 0.26 * length
    neck_end = front + 0.34 * length
    chamfer = 0.15 * length

    neck_w = 0.62 * w
    face_w = 1.08 * w

    upper = [
        (face, face_w),                 # flat front face
        (flare_end, neck_w),            # flare back to the neck
        (neck_end, neck_w),             # the neck
        (neck_end, w),                  # step out to the body — the shoulder
        (back - chamfer, w),            # body at full width
        (back, w * 0.55),               # tapered back
    ]
    out = [("poly", _mirror(upper), True)]

    mark = ERS_MARKS.get(int(angle))
    if mark == "cross":                                   # 19°-20°
        out += [("line", (flare_end, neck_w), (face, -face_w)),
                ("line", (flare_end, -neck_w), (face, face_w))]
    elif mark == "diagonal":                              # 26°-30°
        out += [("line", (flare_end, -neck_w), (face, face_w))]
    elif mark == "wedge":                                 # 50°
        out += [("poly", [(face, face_w), (flare_end, 0.0), (face, -face_w)], False)]
    elif mark == "rings":                                 # 70°-90°
        for t in (0.34, 0.68):
            x = face + t * (flare_end - face)
            out += [("line", (x, face_w * 0.92), (x, -face_w * 0.92))]
    return out


def ers_zoom(angle=30, **kw):
    """§6.1.11 variable focus — the same body carrying a Z."""
    out = enhanced_ers(angle, **kw)
    return out + [("text", (0.0, 0.0), "Z", 0.30)]


# --------------------------------------------------------------- §6.2 Fresnel

def fresnel(size_in=6):
    """§6.2. Rounded back, straight body, and a lens ring standing proud at the
    front — the ring is what distinguishes a Fresnel from an ERS at a glance."""
    width = 0.055 * size_in + 0.16
    length = width * 1.5
    w = width / 2
    front = -0.58 * length
    back = length + front
    ring = front + 0.20 * length
    upper = [
        (front, w * 1.18),          # the lens ring, wider than the body
        (ring, w * 1.18),
        (ring, w),
        (back - 0.18 * length, w),
        (back, w * 0.55),           # rounded/chamfered back
    ]
    return [("poly", _mirror(upper), True)]


def _double_arrow(p1, p2, head=0.10):
    """A double-headed arrow from p1 to p2 in (along-axis, cross-axis) feet.

    §6.3.2 draws lamp-axis orientation this way and says it shows "where beam
    lands or filament orientation". The ARROWHEADS are the meaning: a plain bar
    could be read as lens rotation, which is the opposite claim, and the two are
    indistinguishable once drawn. Both heads, always.
    """
    (a1, c1), (a2, c2) = p1, p2
    da, dc = a2 - a1, c2 - c1
    L = math.hypot(da, dc) or 1e-9
    ua, uc = da / L, dc / L
    na, nc = -uc, ua                      # unit normal
    out = [("line", p1, p2)]
    for (ta, tc), sign in (((a2, c2), -1), ((a1, c1), 1)):
        ba, bc = ta + sign * ua * head, tc + sign * uc * head
        out.append(("line", (ta, tc), (ba + na * head * 0.5, bc + nc * head * 0.5)))
        out.append(("line", (ta, tc), (ba - na * head * 0.5, bc - nc * head * 0.5)))
    return out


def oval_beam_fresnel(length=1.05, width=0.72, rotation=None):
    """§6.2 "Oval Beam Fresnel" — which is what an ETC Source Four PARNel is.

    A PARNel is ETC's oval-beam unit: a PAR-style body with a Fresnel-type lens
    that throws a soft oval, and a lens that ROTATES so the oval can be turned.
    RP-2 has no "PARNel" but it has this, and it is the same instrument class.

    Distinctive against a plain Fresnel: shorter and squatter, with a lens flange
    that stands proud and is clearly WIDER than the body.

    `rotation` in degrees adds the oval-axis arrow (§6.3.2 — double-headed,
    because it states where the beam lands, not how the lens is turned). An oval beam that nobody has
    been told the angle of is an oval beam somebody will hang wrong, and §6.14.4
    requires an axis note for PAR lamps for exactly this reason.
    """
    w = width / 2
    front = -0.55 * length
    back = length + front
    flange = front + 0.17 * length
    upper = [
        (front, w * 1.22),            # lens flange, proud and wider than the body
        (flange, w * 1.22),
        (flange, w),
        (back - 0.22 * length, w),
        (back - 0.06 * length, w * 0.82),   # curved back, two chords
        (back, w * 0.40),
    ]
    out = [("poly", _mirror(upper), True)]
    if rotation is not None:
        # The oval-axis bar goes across the BODY, not the lens flange — the
        # flange is only a fifth of the length deep, so a tilted bar drawn there
        # collapses to nothing. Sized to stay inside the outline at any angle.
        a = math.radians(rotation)
        body_half_len = (back - flange) / 2
        cx = (flange + back) / 2
        r = min(w * 0.82 / max(abs(math.cos(a)), 1e-6),
                body_half_len * 0.82 / max(abs(math.sin(a)), 1e-6))
        out += _double_arrow((cx - r * math.sin(a), -r * math.cos(a)),
                             (cx + r * math.sin(a), r * math.cos(a)),
                             head=min(0.11, r * 0.42))
    return out


# ------------------------------------------------------------------- §6.3 PAR

# §6.3.2: the beam spread is a MARK ON THE FRONT, and §6.14.4 adds a lamp-axis
# rotation arrow — a PAR's filament has an orientation and the electrician needs it.
PAR_MARKS = {"XWFL": "square", "WFL": "triangle", "MFL": "bar",
             "NSP": "narrow", "VNSP": "cross"}


def par(lamp=64, spread="MFL"):
    """§6.3. A rounded capsule sized by lamp, with the beam spread marked on the
    front per §6.3.2. §6.14.4 also requires a lamp-axis arrow, which the plot
    adds as an annotation rather than as part of the symbol."""
    width = {16: 0.17, 38: 0.33, 46: 0.40, 56: 0.48, 64: 0.65}.get(lamp, 0.65)
    length = width * 1.35
    w = width / 2
    front = -0.55 * length
    back = length + front
    r = w * 0.55
    upper = [
        (front, w),
        (back - r, w),
        (back - r * 0.3, w * 0.85),      # rounded back, three chords
        (back, w * 0.45),
    ]
    out = [("poly", _mirror(upper), True)]

    m = PAR_MARKS.get(spread)
    d = 0.30 * length
    if m == "cross":
        out += [("line", (front + d, w), (front, -w)), ("line", (front + d, -w), (front, w))]
    elif m == "narrow":
        out += [("line", (front + d, -w), (front, w))]
    elif m == "triangle":
        out += [("poly", [(front, w), (front + d, 0.0), (front, -w)], False)]
    elif m == "square":
        out += [("poly", [(front + 0.08 * length, w * 0.55), (front + d, w * 0.55),
                          (front + d, -w * 0.55), (front + 0.08 * length, -w * 0.55)], True)]
    elif m == "bar":
        out += [("line", (front + d * 0.6, w * 0.8), (front + d * 0.6, -w * 0.8))]
    return out


# --------------------------------------------------------- §6.16 LED fixtures

def led(colors=7, length=1.5, width=0.62):
    """§6.16. Dots inside the body — THE NUMBER OF DOTS IS THE NUMBER OF COLORS.

    A Lustr's x7 array is seven dots; an ADJ Mega Tri Bar is three.
    """
    back, front = 0.40 * length, -0.60 * length
    w = width / 2
    upper = [(back - 0.12 * length, w * 0.5), (back, w * 0.9), (back, w), (front, w)]
    out = [("poly", _mirror(upper), True)]
    # lay the dots out in the front half, in rows, the way the plate shows
    n = max(1, int(colors))
    per_row = 1 if n <= 1 else (2 if n <= 4 else 3)
    rows = math.ceil(n / per_row)
    placed = 0
    for r in range(rows):
        a = front + (0.20 + 0.16 * r) * length
        k = min(per_row, n - placed)
        for i in range(k):
            c = 0 if k == 1 else (-w * 0.45 + i * (w * 0.9 / (k - 1)))
            out.append(("circle", (a, c), width * 0.045, True))
            placed += 1
    return out


# ------------------------------------------------- §6.8 automated luminaires

def moving_head(kind="wash", body=0.95, swing=1.45):
    """§6.8.2. Moving yoke / head. Drawn inside a DASHED SWING-RADIUS circle —
    RP-2: "should approximate size, shape, and swing radius." The dashed circle
    is the useful part: it is the space the unit needs to not hit anything."""
    w = body / 2
    out = [("circle", (0.0, 0.0), swing / 2, "dashed")]
    nose = -w * 1.05
    upper = [(nose, w * 0.72), (-w * 0.55, w), (w * 0.55, w), (w, w * 0.6)]
    out += [("poly", _mirror(upper), True)]
    if kind == "yoke":
        out += [("text", (0.0, 0.0), "Y", 0.26)]
    elif kind == "spot":
        out += [("line", (nose, w * 0.55), (nose, -w * 0.55))]
    return out


# ------------------------------------------------------------- §6.9 practical

def practical(size=0.5):
    """§6.9. A triangle. Nothing else."""
    h = size
    return [("poly", [(h * 0.5, 0.0), (-h * 0.5, h * 0.55), (-h * 0.5, -h * 0.55)], True)]


# --------------------------------------------------------------- §6.10 / 6.6

def followspot(length=2.4, width=0.9):
    """§6.10. A long body with a stepped waist."""
    back, front = 0.45 * length, -0.55 * length
    w = width / 2
    upper = [(back - 0.10 * length, w * 0.55), (back, w * 0.8), (back, w * 0.8),
             (back - 0.42 * length, w * 0.8), (back - 0.48 * length, w),
             (front + 0.12 * length, w), (front, w * 0.78)]
    return [("poly", _mirror(upper), True)]


def cyc_unit(cells=3, cell=1.0, depth=0.75, focus=True):
    """§6.6.2. Rectangles divided into cells — one box per cell.

    RP-2 draws these as plain divided rectangles that "approximate an accurate
    size & shape", so `cell` and `depth` should be the real unit's dimensions
    rather than a house style.

    §6.6.1 shows the FOCUS DIRECTION as an arrow BESIDE the unit, not inside it.
    It matters more here than on any other symbol: a cyc light is asymmetric and
    aimed up the cloth, so which way it faces is the whole of its behaviour, and
    the body is a rectangle that looks identical either way round.
    """
    total = cells * cell
    out = []
    for i in range(cells):
        a0 = depth / 2
        c0 = -total / 2 + i * cell
        out.append(("poly", [(a0, c0), (a0, c0 + cell),
                             (-a0, c0 + cell), (-a0, c0)], True))
    if focus:
        tip, tail = -depth * 1.45, -depth * 0.78
        out.append(("line", (tail, 0.0), (tip, 0.0)))
        for side in (1, -1):
            out.append(("line", (tip, 0.0),
                        (tip + depth * 0.30, side * depth * 0.20)))
    return out


def striplight(length=6.0, depth=0.6, lamp="PAR 38", mount="pipe"):
    """§6.7.1. A long shallow body with a small tab at ONE end.

    **Length follows the real unit.** RP-2 is explicit: "Overall length of the
    instrument dependent on number of lamps. Measure the instruments." A strip
    drawn at a default length is the one symbol on a plot that is guaranteed
    wrong, because its length is the information.

    §6.7.2 distinguishes the mounting: `mount="pipe"` is hung, `mount="trunnion"`
    is a ground row and carries a second line along the back. An electrician
    reading a ground row as a hung unit hangs it.
    """
    a, c = depth / 2, length / 2
    tab = min(depth * 0.55, length * 0.10)
    out = [("poly", [(a, -c), (a, c - tab), (a + depth * 0.32, c - tab),
                     (a + depth * 0.32, c), (-a, c), (-a, -c)], True)]
    if mount == "trunnion":
        out.append(("line", (-a + depth * 0.22, -c * 0.94),
                    (-a + depth * 0.22, c * 0.94)))
    return out


# ------------------------------------------------------- §6.13 accessories

# RP-2 §6.13 lists ten accessory symbols. Only these four are drawn, because
# Jerry said 2026.09.23 that beam projectors, scoops and fluorescents are
# "basically gone" and asked for barn doors and top hats. The standard is from
# 2006 and still treats all of them as current; the working designer is the
# better authority on what is still in a rental stock.
#
# All four hang on a MOUNTING LINE that stands proud of the body at top and
# bottom — on the plate that line is the gel-frame edge they clip into, and it
# is what makes an accessory read as attached rather than as a second object
# floating in front of the instrument.


def barn_door(panels=2, size=0.55, flare=1.55):
    """§6.13. Two-panel is an OPEN trapezoid; four-panel is CLOSED at the front.

    That is the whole of the distinction on the plate, and it is enough: the
    reader is being told how many flaps there are, not what they look like.
    """
    w = size / 2
    d = size * 0.95
    out = [("line", (0.0, -w), (0.0, w)),
           ("line", (0.0, w), (-d, w * flare)),
           ("line", (0.0, -w), (-d, -w * flare))]
    if panels >= 4:
        out.append(("line", (-d, w * flare), (-d, -w * flare)))
    return out


def top_hat(size=0.5, half=False):
    """§6.13. A square on its mounting line; a half hat is that square cut corner
    to corner, so the two read apart at a glance even at 1/2" scale."""
    w = size / 2
    out = [("line", (0.0, -w * 1.55), (0.0, w * 1.55))]      # gel-frame edge, proud
    if half:
        out.append(("poly", [(0.0, w), (0.0, -w), (-size, -w)], True))
    else:
        out.append(("poly", [(0.0, -w), (-size, -w), (-size, w), (0.0, w)], True))
    return out


# --------------------------------------------- attaching accessories to a unit

# RP-2 puts accessories in two DIFFERENT places, and the difference is physical:
#
#   Gate accessories (§6.1.11, §6.14.2) go INSIDE the body — a gobo, an iris and
#   a rotator all sit at the gate, behind the lens, and RP-2 marks them with a
#   filled circle, an open circle and an R.
#
#   Front-of-lens accessories (§6.13) go at the FRONT — barn doors, hats,
#   scrollers and dousers all clip onto the colour frame.
#
# So the designer says only WHAT is on the unit; where the mark goes is the
# drawing's job, not theirs. One field on the instrument, two placements.

_GATE = {"gobo": "template", "template": "template", "pattern": "template",
         "gobo rotator": "rotator", "rotator": "rotator", "double rotator": "rotator2",
         "iris": "iris"}

_FRONT = {"top hat": "tophat", "tophat": "tophat", "hat": "tophat",
          "half hat": "halfhat", "halfhat": "halfhat", "half top hat": "halfhat",
          "barn door": "bd4", "barndoor": "bd4", "barn doors": "bd4",
          "barn door 2": "bd2", "2 panel barn door": "bd2", "bd2": "bd2",
          "barn door 4": "bd4", "4 panel barn door": "bd4", "bd4": "bd4"}


def _norm_acc(name):
    import re as _re
    t = _re.sub(r"[^a-z0-9 ]+", " ", str(name or "").lower())
    t = _re.sub(r"\b(\d+)\s*(way|panel|leaf)\b", r"\1", t)
    return _re.sub(r"\s+", " ", t).strip()


def resolve_accessory(name):
    """('gate'|'front'|None, key, note). Never guesses: an unknown accessory is
    reported, because a barn door nobody ordered is a barn door nobody brings."""
    t = _norm_acc(name)
    if not t:
        return None, None, "empty accessory"
    if t in _GATE:
        return "gate", _GATE[t], ""
    if t in _FRONT:
        return "front", _FRONT[t], ""
    # "4 way barn door" -> "4 barn door"; try the words in either order
    if "barn" in t and "door" in t:
        return "front", ("bd2" if "2" in t else "bd4"), f"{name!r} read as a barn door"
    if "hat" in t:
        return "front", ("halfhat" if "half" in t else "tophat"), f"{name!r} read as a hat"
    return None, None, (f"{name!r} is not an accessory this tool knows — "
                        "add it to _GATE or _FRONT in symbols.py")


def _extent(prims):
    """(min_a, max_a) of a symbol, so a front accessory can be put at its nose."""
    vals = []
    for p in prims:
        if p[0] in ("poly", "fill"):
            vals += [q[0] for q in p[1]]
        elif p[0] == "line":
            vals += [p[1][0], p[2][0]]
        elif p[0] in ("circle", "text"):
            vals.append(p[1][0])
    return (min(vals), max(vals)) if vals else (0.0, 0.0)


def with_led_source(prims, colors, width=0.625):
    """Add §6.16 source dots at the LAMP HOUSING of an existing symbol.

    ⭐ THE SYMBOL DOES NOT CHANGE. A Source Four with a 4WRD in it is the same
    barrel, the same lens tube and the same beam angle — so it keeps the same
    outline and gains the dots that say what is making the light. That is how
    USITT's Lighting Documentation Recommended Practice (February 2025) draws
    it: its fixture key lists "CONVENTIONAL ERS 26-DEGREE" and "LED ERS
    26-DEGREE" as the same body, one with dots at the back.

    ⚠ AT THE BACK, WHICH IS WHERE THE LAMP IS. +a is toward the lamp housing;
    the lens is at -a. Putting them at the front would be drawing the source at
    the end the light comes out of, and would also land them on top of §6.1.11's
    gate mark for a gobo.
    """
    n = max(1, int(colors))
    front_a, back_a = _extent(prims)
    span = back_a - front_a
    # Just inside the tapered back — far enough forward that the dots sit on
    # full-width body rather than in the chamfer.
    a = back_a - 0.10 * span
    r = width * 0.045
    w = width / 2
    out = list(prims)
    if n == 1:
        out.append(("circle", (a, 0.0), r, True))
        return out
    # More than one: a row across the body, the way the §6.16 plate lays them.
    for i in range(n):
        c = -w * 0.45 + i * (w * 0.9 / (n - 1))
        out.append(("circle", (a, c), r, True))
    return out


def with_accessories(prims, accessories, size=0.5):
    """Return prims plus every accessory, each drawn where RP-2 puts it.

    Returns (prims, unknown) — `unknown` is the list of names that resolved to
    nothing, so the caller can SAY so rather than dropping them silently.
    """
    if not accessories:
        return list(prims), []
    front_a, _ = _extent(prims)
    out, unknown, n_front = list(prims), [], 0
    gate_at = front_a * 0.42          # inside the body, behind the lens
    for name in accessories:
        where, key, note = resolve_accessory(name)
        if where is None:
            unknown.append(note or str(name)); continue
        if where == "gate":
            if key == "template":
                out.append(("circle", (gate_at, 0.0), size * 0.17, True))
            elif key == "iris":
                out.append(("circle", (gate_at, 0.0), size * 0.17))
            else:
                out.append(("text", (gate_at, 0.0), "RR" if key == "rotator2" else "R", 0.011))
        else:
            # Stack front accessories nose-outward so two never overlap.
            off = front_a - n_front * size * 1.15
            n_front += 1
            shape = (barn_door(2, size) if key == "bd2" else
                     barn_door(4, size) if key == "bd4" else
                     top_hat(size, half=(key == "halfhat")))
            out += [_shift(pr, off) for pr in shape]
    return out, unknown


def _shift(prim, da):
    """Move one primitive along the instrument axis by `da` feet."""
    k = prim[0]
    if k == "poly":
        return (k, [(a + da, c) for a, c in prim[1]], prim[2])
    if k == "line":
        return (k, (prim[1][0] + da, prim[1][1]), (prim[2][0] + da, prim[2][1]))
    return (k, (prim[1][0] + da, prim[1][1])) + tuple(prim[2:])


# ------------------------------------------------------------- §6.12 booms

def boom_mount(kind="boom-base", size=1.4):
    """§6.12 — how a boom meets the floor, drawn in PLAN.

        floor-plate   a square around the unit
        boom-base     a large circle (the base plate seen from above)
        flange        a small circle with a crosshair

    It is not decoration: a floor plate needs floor space and a sandbag, a flange
    is a permanent fitting, and an electrician reading one as the other brings
    the wrong hardware.
    """
    k = (kind or "boom-base").strip().lower().replace("_", "-")
    if k in ("floor-plate", "plate", "floorplate"):
        h = size / 2
        return [("poly", [(h, -h), (h, h), (-h, h), (-h, -h)], True)]
    if k in ("flange", "flange-mount"):
        r = size * 0.18
        return [("circle", (0.0, 0.0), r),
                ("line", (-r * 1.9, 0.0), (r * 1.9, 0.0)),
                ("line", (0.0, -r * 1.9), (0.0, r * 1.9))]
    r = size / 2
    return [("circle", (0.0, 0.0), r), ("circle", (0.0, 0.0), r * 0.16)]


def radius(prims):
    """The farthest any part of a symbol reaches from its yoke, in feet.

    Notation has to clear the SYMBOL, and symbols are not one size: an ERS is
    1'-8" long, a PAR is squat, a striplight is six feet. A fixed offset put the
    channel circle on top of the instrument for the long ones. And because the
    symbol rotates with its focus, the clearance has to be radial — a distance,
    not a direction.
    """
    best = 0.0
    for p in prims:
        # ⚠ Match the kind explicitly. The old version treated anything that was
        # not a poly or a line as a single point, so adding the "fill" primitive
        # made it try to unpack a whole point LIST as one (a, c) pair. A
        # fall-through default is a bug waiting for the next primitive.
        kind = p[0]
        if kind in ("poly", "fill"):
            pts, pad = p[1], 0.0
        elif kind == "line":
            pts, pad = [p[1], p[2]], 0.0
        elif kind == "circle":
            pts, pad = [p[1]], p[2]
        elif kind == "text":
            pts, pad = [p[1]], 0.0
        else:
            continue
        for a, c in pts:
            best = max(best, math.hypot(a, c) + pad)
    return best


def hatch(prims, spacing=0.09, angle_deg=45.0):
    """Diagonal fill lines across a symbol's bounding box.

    §6.12: "Hatch or shade acceptable for top view of boom." A boom's units are
    stacked vertically, so in plan they land on top of each other — hatching is
    what tells the reader this is a pile of instruments at one point rather than
    one instrument.
    """
    a0, a1 = _extent(prims)
    cs = [q[1] for p in prims if p[0] == "poly" for q in p[1]]
    if not cs:
        return []
    c0, c1 = min(cs), max(cs)
    out, t = [], math.tan(math.radians(angle_deg)) or 1.0
    span = (a1 - a0) + (c1 - c0) / t
    n = max(1, int(span / spacing))
    for i in range(n + 1):
        a = a0 + i * spacing
        # clip the diagonal to the box
        p1 = (max(a0, min(a1, a)), c0)
        p2a = a - (c1 - c0) / t
        if p2a < a0:
            p2 = (a0, c0 + (a - a0) * t)
        else:
            p2 = (p2a, c1)
        if p2[1] > c1:
            continue
        if a0 <= p1[0] <= a1 and a0 <= p2[0] <= a1:
            out.append(("line", p1, p2))
    return out


# ---------------------------------------------------- shading the rear

def _clip_behind(pts, cut):
    """The part of a closed polygon with along-axis >= cut (Sutherland-Hodgman)."""
    out = []
    n = len(pts)
    for i in range(n):
        a0, c0 = pts[i]
        a1, c1 = pts[(i + 1) % n]
        in0, in1 = a0 >= cut, a1 >= cut
        if in0:
            out.append((a0, c0))
        if in0 != in1 and a1 != a0:
            t = (cut - a0) / (a1 - a0)
            out.append((cut, c0 + t * (c1 - c0)))
    return out


def shade_rear(prims, frac=0.30):
    """A SOLID BLACK rear on the body — §6.15's arc-source mark.

    ⭐ RP-2 blackens the back of the symbol for arc sources (HMI and the like),
    and §6.0 sanctions the technique generally: "Further differentiation or
    notation may be necessary to distinguish between luminaires of approximately
    the same size. This may include SHADING THE SYMBOL..."

    Jerry, 2026.09.23, uses the same mark for a 750W Source Four: "I've never
    seen [wattage] on plots except for 750w S4 where the back is blackened —
    like they have for HMI lamps in the spec."

    ⚠ So one mark carries two meanings depending on the plot, which is exactly
    why the INSTRUMENT KEY has to say which. A shaded symbol nobody explained is
    a symbol read as the other thing.
    """
    bodies = [p for p in prims if p[0] == "poly" and p[2]]
    if not bodies:
        return []
    pts = max(bodies, key=lambda p: len(p[1]))[1]
    lo = min(a for a, _ in pts)
    hi = max(a for a, _ in pts)
    cut = hi - (hi - lo) * frac
    back = _clip_behind(list(pts), cut)
    return [("fill", back)] if len(back) >= 3 else []


# ------------------------------------------------------------------ drawing

def draw(sheet, prims, x, y, rotate_deg=0.0, width=None):
    """Draw primitives onto a scaled_pdf.Sheet at (x, y) feet, pointing `rotate_deg`.

    0° points the instrument toward -y (downstage). RP-2 §2.2 allows orienting a
    symbol either to its focus point or to a 90° axis.
    """
    # §6.18: a luminaire is a HEAVY line — it is a thing that physically exists.
    # ⚠ Ask the SHEET, not the module table. The table is the standard; the
    # sheet is what this plot actually draws with, and reading the constant
    # here meant a plot that dialled the heavy weight down got thinner pipes
    # and full-weight instruments — the one place the difference is most
    # obvious. Falls back to the standard for any caller without a sheet.
    if width is not None:
        lw = width
    else:
        try:
            lw = sheet.style("luminaire")[0]
        except AttributeError:
            from .scaled_pdf import LINE_STYLES
            lw = LINE_STYLES["luminaire"][0]
    a = math.radians(rotate_deg)
    ca, sa = math.cos(a), math.sin(a)

    def T(pa, pc):
        # local (along-axis, cross-axis) -> plot (x, y); -a is the front, so the
        # instrument points toward -y when unrotated
        lx, ly = pc, pa
        return (x + lx * ca - ly * sa, y + lx * sa + ly * ca)

    # ⭐ Paint every closed body FIRST, in white, so the instrument occludes the
    # pipe it hangs from. Jerry, 2026.09.23: "the instrument has to be drawn so
    # that the pipe does not go through it — as if the instrument is above it,
    # even though it's not." Two payoffs: the symbol reads as one object, and the
    # body becomes white space a unit number can live in.
    if hasattr(sheet, "fill_poly"):
        for p in prims:
            if p[0] == "poly" and p[2]:
                sheet.fill_poly([T(*q) for q in p[1]])

    for p in prims:
        kind = p[0]
        if kind == "fill":
            if hasattr(sheet, "fill_poly"):
                sheet.fill_poly([T(*q) for q in p[1]], color=_black())
            continue
        if kind == "poly":
            pts = [T(*q) for q in p[1]]
            closed = p[2]
            for i in range(len(pts) - 1 + (1 if closed else 0)):
                q1, q2 = pts[i], pts[(i + 1) % len(pts)]
                sheet.line(q1[0], q1[1], q2[0], q2[1], width=lw)
        elif kind == "line":
            q1, q2 = T(*p[1]), T(*p[2])
            sheet.line(q1[0], q1[1], q2[0], q2[1], width=lw * 0.8)
        elif kind == "circle":
            q = T(*p[1])
            dashed = len(p) > 3 and p[3] == "dashed"
            filled = len(p) > 3 and p[3] is True
            sheet.circle(q[0], q[1], p[2], width=lw * (0.45 if dashed else 0.8),
                         fill=None, dash=(2, 2) if dashed else None)
            if filled:
                sheet.circle(q[0], q[1], p[2], width=0.3, fill=_black())
        elif kind == "text":
            q = T(*p[1])
            sheet.text(q[0], q[1], p[2], size=p[3] * 26, center=True, bold=True)


def _black():
    from reportlab.lib.colors import black
    return black


# ------------------------------------------------------ §6.14 luminaire notation

def for_type(kind, lens_rotation=None, lamp=None):
    """Pick a symbol from a fixture-table key like "S4 26" or "Lustr 26 EDLT".

    lens_rotation (degrees) is used by oval-beam units — a PARNel's lens turns,
    and the angle is information the electrician needs, not decoration.

    ⭐ `lamp` is here because a RETROFIT changes what is making the light without
    changing the fixture (Jerry, 2026.09.29). Pull the HPL out of a Source Four,
    drop a 4WRD in, and the plot used to draw a tungsten unit — indistinguishable
    from the one beside it that still has an HPL. The barrel is the same; the
    source is not, and §6.16 has a way to say so.
    """
    k = (kind or "").strip()
    # Resolve a paperwork name to a table key first — "ETC Source4 36deg" should
    # draw exactly what "S4 36" draws, not something the loose matcher guessed.
    try:
        from .fixture_names import resolve
        from . import photometrics as _ph
        _key, _ = resolve(k, _ph.FIXTURES)
        if _key:
            k = _key
    except Exception:
        pass
    low = k.lower()
    import re as _re
    # ⚠ "S4 26" must not parse as 4 degrees. Strip the product names that carry
    # a digit — Source4, S4, PAR 64, MR-16 — before looking for the beam angle.
    cleaned = _re.sub(r"(source\s*4|s4|par\s*\d+|mr-?\d+|\bx7\b|series\s*\d)", " ",
                      low, flags=_re.I)
    n = _re.findall(r"(\d+(?:\.\d+)?)\s*(?:deg|°)?", cleaned)
    deg = float(n[0]) if n else 26.0

    if "cyc" in low:
        return cyc_unit(3)
    if "lustr" in low or "colorsource" in low or "clrsrc" in low or "led" in low:
        # §6.16: dots = number of colors. A Lustr is the x7 array; ColorSource
        # is five — red, green, blue, lime, indigo — per ETC's own datasheets.
        colors = 7 if "lustr" in low else (5 if ("colorsource" in low or "clrsrc" in low) else 4)
        return led(colors)
    if "parnel" in low or "oval" in low:
        # An oval beam needs its axis called out. Default to level — the
        # commonest hang, and what an electrician assumes if nobody says.
        return oval_beam_fresnel(rotation=lens_rotation if lens_rotation is not None else 0)
    if "par" in low:
        spread = next((s for s in ("VNSP", "XWFL", "WFL", "MFL", "NSP") if s in k.upper()), "MFL")
        lamp = 64 if "64" in k else (56 if "56" in k else 64)
        return par(lamp, spread)
    if "fresnel" in low or "fres" in low:
        size = 8 if "8" in k else 6
        return fresnel(size)
    if "strip" in low:
        return striplight()
    if "mac" in low or "mover" in low or "moving" in low or "aura" in low:
        return moving_head("wash")
    if "zoom" in low:
        return _with_lamp(ers_zoom(deg), lamp)
    # default: an ellipsoidal at whatever angle the name carries
    return _with_lamp(enhanced_ers(deg), lamp)


def _with_lamp(prims, lamp):
    """Dots at the lamp housing when the lamp is an LED retrofit.

    ⚠ HOW MANY comes from photometrics, not from a list here — the same reason
    the footprint and the multipliers do. A second copy of "a 4WRD is one
    colour" is a second thing to keep in step.
    """
    if not lamp:
        return prims
    try:
        from . import photometrics as _ph
        n = _ph.lamp_colors(lamp)
    except Exception:
        return prims
    return with_led_source(prims, n) if n else prims


# §6.14.1 gives THREE house control models, and they are notated differently.
# Jerry, 2026.09.23: "most houses have circuit per dimmer" — so that is the
# default here, and it is the one where the third container is WRONG rather than
# merely absent.
CONTROL_MODELS = ("dimmer-per-circuit", "hard-and-soft-patch", "no-soft-patch",
                  "dimmer-is-address")


def notation(sheet, x, y, *, channel=None, circuit=None, dimmer=None, address=None,
             color=None, purpose=None, unit=None, wattage=None,
             control="dimmer-per-circuit", rotate_deg=0.0, body_center=0.0,
             size=0.42, gap=0.30, above=1.0):
    """§6.14.1 — the SHAPE of the container carries the meaning.

        hexagon    circuit — or, on a unit with an address and no dimmer, the
                   ADDRESS, because that is what controls it (see below)
        rectangle  dimmer (in a patch-panel house), or the circuit when the
                   hexagon has been given to an address
        circle     channel

    ⭐ How many containers there are depends on the HOUSE, per §6.14.1:

      `dimmer-per-circuit`   Most houses (Jerry, 2026.09.23). The circuit is
                             hard-wired to its own dimmer, so the two numbers are
                             ONE fact. RP-2 draws a single hexagon and labels it
                             "Circuit & Dimmer". **Drawing two containers here is
                             not tidy-but-redundant — it tells the electrician
                             there is a patch to make, and there is not.**
      `hard-and-soft-patch`  Hexagon (circuit), rectangle (dimmer), circle
                             (channel). All three, because all three differ.
      `no-soft-patch`        Hexagon (circuit) and circle (dimmer). The console
                             addresses dimmers directly; there is no channel
                             number distinct from the dimmer.
      `dimmer-is-address`    Jerry, 2026.09.29: "in ETC world, a dimmer is a DMX
                             shape — basically one address with the value of
                             intensity." The dimmer NUMBER stops being a
                             separate fact: it is the address, so the hexagon
                             carries the address and the rectangle the circuit,
                             exactly as it does for an LED. ⭐ The consequence
                             is that a conventional rig and an LED rig are
                             notated the same way, which is the point — on a
                             mixed plot the reader stops having to know which
                             kind of unit they are looking at to read the
                             number.

    §6.14.2 stacks them below the symbol, with focus and color above it.

    RP-2's own caveat, worth honouring: "Notation shown on any plot is a
    case-by-case basis. It is not necessary to include all categories, when the
    combination runs the risk of making the plot's appearance cluttered." So
    anything passed as None is simply not drawn.
    """
    import math as _m
    from reportlab.lib.colors import black

    _r = _m.radians(rotate_deg)
    _sa, _ca = _m.sin(_r), _m.cos(_r)

    def _along(d):
        return (x - d * _sa, y + d * _ca)


    # above the symbol: color, then purpose (focus)
    # ⭐ COLOUR AND FOCUS GO IN FRONT, ACROSS THE LENS — §6.14.2 draws them beyond
    # the lens end, and Jerry, 2026.09.24: "the colour label should be along the
    # width of the lens in the front."
    #
    # ⚠ They used to sit at a fixed +y regardless of where the unit pointed, so
    # on a unit aimed downstage they landed BEHIND it. Front is -a, whichever way
    # the symbol has turned.
    # ⭐ COLOUR AND FOCUS GO IN FRONT, ACROSS THE LENS. Jerry, 2026.09.24: "the
    # colour label should be along the width of the lens in the front." §6.14.2
    # draws them beyond the lens of an instrument that points up the page.
    #
    # ⚠ Each further line steps FURTHER OUT ALONG THE AXIS, not down the page.
    # Stepping down the page walks the second line back toward the unit on
    # anything aimed upstage — the same class of error as the stack below.
    #
    # ⚠ `above` clears the SYMBOL, not the label. A label anchored exactly at the
    # clearance still overlaps, because the glyphs grow back toward the unit:
    # "R52+R119" sat on the top hat of the GRID C unit. How far it reaches
    # depends on which way the unit aims — a unit pointing downstage needs the
    # cap height, one pointing stage left needs half the STRING WIDTH, which for
    # a two-colour string is several times more.
    _tp = getattr(sheet, "pt_per_ft", None)
    _h = (7 / _tp) if _tp else 0.30          # cap height in feet

    # ⚠ A CENTRED label is right in front of a unit aimed up or downstage and
    # wrong in front of one aimed to a side. Centring puts HALF the string on
    # the far side, so clearing the symbol means pushing the whole label out by
    # half its width — "R52+R119" ended up 2'-5" from a unit whose neighbours
    # sat at 1'-6", which is what made the sideways units look unlike the rest.
    # Anchor the INNER EDGE instead and let the label run outward. Same reason
    # Sheet.text grew `align` for the boom height labels.
    _across = abs(_sa) > abs(_ca)            # the axis runs across the page
    _align = ("left" if _sa > 0 else "right") if _across else "center"

    d = -(above + (0.0 if _across else _h / 2))
    fx, fy = _along(d)
    # A second line stacks DOWN THE PAGE next to a sideways unit, and further
    # OUT along the axis in front of a vertical one — stacking down the page
    # there would walk it back through a unit aimed upstage.
    step = 0
    for text in [t for t in (color, purpose) if t]:
        if _across:
            sheet.text(fx, fy - step * _h * 1.25, text, size=7, align=_align)
        else:
            gx, gy = _along(d - step * _h * 1.25)
            sheet.text(gx, gy, text, size=7, center=True)
        step += 1

    # ⭐ §6.14.2 puts the INSTRUMENT NUMBER INSIDE THE BODY, with the wattage
    # just below it in the barrel — not in the stack underneath. Jerry asked for
    # the same thing 2026.09.23 ("move the unit number onto the center of the
    # unit"), which is the plate.
    #
    # Drawn at the symbol's ORIGIN — the yoke — because that is the one point
    # that does not move when the symbol rotates to its focus. The text itself
    # stays horizontal: RP-2 p.1, "the associated text should be properly
    # oriented with the rest of the text in the drawing."
    # ⚠ Not at the origin. The origin is the YOKE, and the yoke is clamped to
    # the pipe — so a number drawn there has a heavy batten line straight through
    # it. The plate puts it in the BODY, behind the yoke, which is where there is
    # white to write on.
    #
    # The offset therefore has to follow the symbol as it rotates. In draw()'s
    # frame a point (pa, 0) lands at (x - pa·sin θ, y + pa·cos θ), so moving
    # +pa goes toward the back of the instrument whichever way it points.
    if unit is not None:
        ux, uy = _along(body_center)
        sheet.text(ux, uy - size * 0.2, str(unit), size=7, center=True, bold=True)
    # ⚠ No wattage on the symbol. Jerry, 2026.09.23: "I've never seen it on
    # plots except for 750w S4 where the back is blackened." §6.14.2 does show a
    # wattage inside the body, but a recommended practice records what MAY be
    # drawn; the working convention is the shaded rear, and that is drawn
    # instead. `wattage` is kept in the signature so callers do not break, and
    # ignored on purpose.

    # ⭐ THE STACK GOES BEHIND THE LIGHT — §6.14.2 puts circuit, dimmer and
    # channel below an instrument that points up, i.e. off its back. Jerry,
    # 2026.09.24: "the channel number should be behind the light, not in front."
    #
    # ⚠ It used to run to a fixed -y, which is the FRONT for a unit aimed
    # downstage — so the channel sat in the beam. Behind is +a.
    # ⚠ Every container steps FURTHER BEHIND along the axis. Stepping down the
    # page put the second and third containers back through the instrument on
    # anything aimed downstage, where behind is +y.
    # + 0.62 size, not 0.5: the hexagon's own corner reaches 0.58 size, so a
    # container centred at the clearance still laps over the symbol.
    d = above + size * 0.62

    # In a dimmer-per-circuit house the circuit and the dimmer are one number,
    # so a dimmer that merely repeats the circuit is not drawn twice.
    if control == "dimmer-per-circuit":
        if circuit is None and dimmer is not None:
            circuit, dimmer = dimmer, None
        elif dimmer is not None and str(dimmer) == str(circuit):
            dimmer = None

    # ⭐ In a dimmer-is-address house the dimmer number IS the address, so a unit
    # that carries both is stating one fact twice. The address is the one that
    # gets drawn — it is universe-qualified, so it cannot be misread as a
    # dimmer — and the dimmer is dropped rather than given a second container.
    #
    # ⚠ A unit with a dimmer and NO address still draws its dimmer. The house
    # being addressable does not mean every unit's address was recorded, and
    # drawing nothing would be worse than drawing the number we have.
    if control == "dimmer-is-address" and address is not None:
        dimmer = None

    # ⭐ THE HEXAGON CARRIES WHAT CONTROLS THE UNIT, THE RECTANGLE WHAT POWERS
    # IT. Jerry, 2026.09.28: "hexagon carries dimmer or address. rectangle
    # carries circuit — which would be an exception."
    #
    # RP-2 §6.14.1 reads the other way round, and it held until LEDs. The plates
    # assume the circuit and the dimmer ARE the control path, which is why a
    # dimmer-per-circuit house collapses them into one hexagon above. A unit on a
    # circuit for POWER and an address for CONTROL is two facts about two
    # different things, and the standard has one container for them.
    #
    # ⚠ Before this, an addressed unit drew NOTHING here. On an all-LED plot the
    # drawing said nothing at all about what anything was plugged into.
    #
    # ⚠ The address arrives universe-qualified from `dmx.plot_number`, which is
    # the disambiguation: a hexagon reading "45" is dimmer 45 and one reading
    # "1/45" is an address. The instrument key names both, so a stranger reading
    # the sheet is told rather than left to infer.
    if address is not None and dimmer is None:
        circuit, dimmer = address, (circuit if circuit is not None else None)

    # The containers themselves stay UPRIGHT and the text horizontal (RP-2 p.1:
    # "the associated text should be properly oriented with the rest of the text
    # in the drawing"). Only where the stack SITS follows the symbol.
    if circuit is not None:
        cx, cy = _along(d)
        pts = [(cx + size * 0.58 * _m.cos(a), cy + size * 0.58 * _m.sin(a))
               for a in [_m.radians(30 + 60 * i) for i in range(6)]]
        for i in range(6):
            p, q = pts[i], pts[(i + 1) % 6]
            sheet.line(p[0], p[1], q[0], q[1], width=0.6)
        sheet.text(cx, cy - size * 0.12, str(circuit), size=6, center=True)
        d += size + gap * 0.5

    if dimmer is not None:
        cx, cy = _along(d)
        sheet.rect(cx - size * 0.62, cy - size * 0.41, size * 1.24, size * 0.82, width=0.6)
        sheet.text(cx, cy - size * 0.24, str(dimmer), size=6, center=True)
        d += size + gap * 0.5

    if channel is not None:
        cx, cy = _along(d)
        sheet.circle(cx, cy, size * 0.52, width=0.6)
        sheet.text(cx, cy - size * 0.12, str(channel), size=6, center=True)
