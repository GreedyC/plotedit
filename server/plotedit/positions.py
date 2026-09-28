"""Hanging positions: which way they run, and which end unit 1 is at.

⭐ UNIT NUMBERS FOLLOW RP-2 §2.3.2, which is explicit:

    "Luminaires on hanging positions perpendicular to centerline (e.g., battens)
     are numbered from STAGE LEFT TO STAGE RIGHT."
    "Luminaires on onstage booms or other vertical hanging positions are numbered
     from top to bottom, downstage to upstage."
    "Luminaires mounted on FOH positions parallel to centerline should number
     starting with the units nearest to plaster line."
    "Luminaires mounted on FOH positions non-parallel to centerline (box booms)
     should number starting with the units closest to centerline."

⚠ CHANNELS ARE A DIFFERENT THING and are NOT covered by the standard. RP-2
requires the channel to be shown on the plot and says outright that channel
hookups are "not addressed in this document." Jerry's channel convention —
**house left to house right**, so channel 1 is at stage right — is his own and
does not conflict with anything. See `channel_order()`.

**Unit numbers and channel numbers therefore run in OPPOSITE directions across a
batten**, which is correct and is not a bug: the unit number is for whoever hangs
the rig, the channel is for whoever sits in the house and reads the plot.

Coordinates, since the rules are expressed in them:

    x increases toward STAGE RIGHT.   y increases UPSTAGE.
    The origin is the downstage-LEFT corner of the room.

So stage left is the MINIMUM x, stage right the maximum, and downstage the
minimum y. Fixed in web/src/geometry.ts and corroborated by the sample plot,
where "Special SR" sits at x=22 and "Special SL" at x=11 in a 33-foot room.
"""
from typing import Any, Dict, List, Optional, Tuple

# The four ends a position can be numbered from.
FROM_SR, FROM_SL, FROM_DS, FROM_US = "SR", "SL", "DS", "US"
# Vertical positions number by height, not by a compass direction.
FROM_TOP, FROM_BOTTOM = "TOP", "BOTTOM"
# §2.3.2, for FOH positions.
FROM_PLASTER = "PLASTER"        # parallel to centerline: nearest the plaster line
FROM_CENTER = "CENTER"          # non-parallel (box booms): nearest centerline


VERTICAL_TYPES = ("boom", "box-boom", "boom-box", "ladder", "tormentor", "torm")

# ⭐ A ladder and a tormentor are vertical, but they do NOT stand on the floor.
# A ladder hangs from a pipe and can be flown, so it has a TRIM and no base; a
# tormentor is bolted to the building beside the proscenium and is not chosen at
# all. Asking either for a boom base is asking for hardware that does not exist.
HANGING_TYPES = ("ladder",)
FIXED_TYPES = ("tormentor", "torm")


def is_vertical(pos: Dict[str, Any]) -> bool:
    """A boom, box boom, ladder or tormentor: a pipe that stands up.

    ⭐ In PLAN a vertical position is a POINT, not a line — every unit on it
    shares one x and y and differs only in height. That is why booms need their
    own everything: the two-dimensional drawing cannot separate the units, so
    RP-2 §6.12 puts the layout beside the plot instead of on it.
    """
    t = (pos.get("type") or "").strip().lower()
    dx = abs(pos.get("x2", pos["x1"]) - pos["x1"])
    dy = abs(pos.get("y2", pos["y1"]) - pos["y1"])
    if t in VERTICAL_TYPES:
        # ⚠ Measure, do not just read the name. "Box boom" covers two different
        # things: a plain vertical pipe in a box (a point, numbered top down) and
        # a rail with real horizontal extent, which §2.3.2 numbers from the units
        # closest to centerline. Trusting the word alone got the second one
        # wrong, and the plot would have looked right.
        return not (dx > 0.5 or dy > 0.5)
    if t:
        return False
    # Untyped: a position with no length is a point, so it stands up.
    return dx < 0.5 and dy < 0.5


def axis(pos: Dict[str, Any]) -> str:
    """'vertical' (a boom), 'lateral' (stage left to right) or 'longitudinal' (US-DS)."""
    if is_vertical(pos):
        return "vertical"
    dx = abs(pos.get("x2", pos["x1"]) - pos["x1"])
    dy = abs(pos.get("y2", pos["y1"]) - pos["y1"])
    return "longitudinal" if dy > dx else "lateral"


def number_from(pos: Dict[str, Any]) -> str:
    """Which end unit 1 sits at. An explicit `numberFrom` always wins.

    The default is the reading direction from the house: house left to house
    right across a lateral position (so stage right first), near to far on a
    longitudinal one (so downstage first). Jerry asked for the override the same
    day — "later we may want to be able to override that" — so the field exists
    now and simply defaults.
    """
    explicit = (pos.get("numberFrom") or "").strip().upper()
    if explicit in (FROM_SR, FROM_SL, FROM_DS, FROM_US, FROM_TOP, FROM_BOTTOM):
        return explicit
    a = axis(pos)
    t = (pos.get("type") or "").strip().lower()

    # §2.3.2: "Luminaires mounted on FOH positions non-parallel to centerline
    # (box booms) should number starting with the units closest to centerline."
    # ⚠ Only when the position HAS horizontal extent. Plenty of houses hang a box
    # boom as a plain vertical pipe, and then every unit is the same distance
    # from centerline and the rule says nothing — so fall through to top-down.
    if t in ("box-boom", "boom-box") and not is_vertical(pos):
        return FROM_CENTER

    if a == "vertical":
        # §2.3.2: "on onstage booms or other vertical hanging positions... from
        # top to bottom, downstage to upstage."
        return FROM_TOP

    # §2.3.2: "FOH positions parallel to centerline should number starting with
    # the units nearest to plaster line."
    if a == "longitudinal" and pos.get("foh"):
        return FROM_PLASTER

    return FROM_DS if a == "longitudinal" else FROM_SL


def _sort_key(pos: Dict[str, Any]):
    """(key, reverse) — how to order units along `pos` so unit 1 comes first."""
    end = number_from(pos)
    if end == FROM_SR:                      # stage right is the MAXIMUM x
        return (lambda i: i.get("x", 0.0)), True
    if end == FROM_SL:
        return (lambda i: i.get("x", 0.0)), False
    if end == FROM_DS:                      # downstage is the MINIMUM y
        return (lambda i: i.get("y", 0.0)), False
    if end == FROM_TOP:
        # §2.3.2: "from top to bottom, downstage to upstage." The second clause
        # is the TIEBREAK — two units at one height on a ladder's two sides are
        # ordered downstage first, which is why a ladder does not need somebody
        # to invent a rule for it.
        return (lambda i: (-(i.get("height", i.get("trim", 0.0)) or 0.0),
                           i.get("y", 0.0))), False
    if end == FROM_BOTTOM:
        return (lambda i: ((i.get("height", i.get("trim", 0.0)) or 0.0),
                           i.get("y", 0.0))), False
    if end == FROM_PLASTER:                 # §2.3.2, FOH parallel to centerline
        return (lambda i: i.get("y", 0.0)), True
    if end == FROM_CENTER:                  # §2.3.2, box booms
        return (lambda i: abs(i.get("x", 0.0) - i.get("_center_x", 0.0))), False
    return (lambda i: i.get("y", 0.0)), True    # US


def order(instruments: List[Dict[str, Any]], pos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The instruments on `pos`, in hanging order — unit 1 first."""
    name = (pos.get("name") or "").strip().lower()
    on = [i for i in instruments if (i.get("position") or "").strip().lower() == name]
    key, rev = _sort_key(pos)
    return sorted(on, key=key, reverse=rev)


def number(instruments: List[Dict[str, Any]], pos: Dict[str, Any],
           start: int = 1) -> Tuple[int, Optional[str]]:
    """Renumber the units on one position in place. Returns (count, warning).

    ⚠ This OVERWRITES unit numbers. On a plot that has been hung, a renumber is
    a different document from the one taped to the pipe, so the caller has to
    mean it. Nothing calls this automatically.
    """
    on = order(instruments, pos)
    if not on:
        return 0, f"no instruments on {pos.get('name')!r}"
    warn = None
    # Two units at the same coordinate cannot be ordered, and picking one
    # arbitrarily is how a plot gets hung backwards. Say so.
    key, _ = _sort_key(pos)

    def _rounded(v):
        # A sort key may be a single number or a tuple — §2.3.2's vertical rule
        # is "top to bottom, DOWNSTAGE TO UPSTAGE", which needs two values. Two
        # units are only genuinely unorderable when the WHOLE key matches.
        return tuple(round(x, 3) for x in v) if isinstance(v, tuple) else (round(v, 3),)

    vals = [_rounded(key(i)) for i in on]
    if len(set(vals)) != len(vals):
        warn = (f"{pos.get('name')!r}: two units share a coordinate along the "
                f"position, so their order is arbitrary — move one or number by hand")
    for n, inst in enumerate(on, start):
        inst["unit"] = n
    return len(on), warn


def describe(pos: Dict[str, Any]) -> str:
    """One line for the plot's notes, so the drawing states its own convention."""
    # Phrased from the house, because that is where it will be read.
    end = {FROM_SR: "stage right (RP-2 numbers battens from stage LEFT — is this deliberate?)",
           FROM_SL: "stage left — RP-2 §2.3.2",
           FROM_DS: "farthest downstage",
           FROM_US: "farthest upstage",
           FROM_TOP: "the highest unit — top to bottom, downstage to upstage",
           FROM_BOTTOM: "the lowest unit — bottom to top",
           FROM_PLASTER: "nearest the plaster line — RP-2 §2.3.2, FOH",
           FROM_CENTER: "nearest centerline — RP-2 §2.3.2, box boom"}[number_from(pos)]
    how = "set" if pos.get("numberFrom") else "default"
    return f"{pos.get('name', '?')}: unit 1 at {end} ({how})"


def check_booms(plot: Dict[str, Any]) -> List[str]:
    """§6.12 rules that a plot can break. Returns plain-English problems.

    RP-2: **"Choose only one type of layout per plot."** Two layouts on one
    drawing means the reader has to work out which convention each boom follows,
    which is exactly the ambiguity the standard exists to remove.
    """
    problems: List[str] = []
    positions = plot.get("positions") or []
    instruments = plot.get("instruments") or []
    booms = [p for p in positions if is_vertical(p)]
    if not booms:
        return problems

    layouts = {(p.get("layout") or plot.get("boomLayout") or "option1") for p in booms}
    if len(layouts) > 1:
        problems.append(
            f"this plot uses {len(layouts)} boom layouts ({', '.join(sorted(layouts))}) "
            f"— RP-2 §6.12: choose only one type of layout per plot")

    for p in booms:
        name = (p.get("name") or "").strip().lower()
        on = [i for i in instruments
              if (i.get("position") or "").strip().lower() == name]
        # ⭐ On a boom the HEIGHT is the only thing separating one unit from
        # another. Without it the unit cannot be drawn, cannot be numbered and
        # cannot be hung — it is not a missing nicety, it is the position.
        missing = [i.get("unit") for i in on if i.get("height") is None]
        if missing:
            problems.append(
                f"{p.get('name')}: units {', '.join(str(u) for u in missing)} have no "
                f"height. On a boom every unit shares one x and y, so the height is "
                f"the only thing that tells them apart — and the only thing to hang by")
        if len(on) > 1:
            hs = [i.get("height") for i in on if i.get("height") is not None]
            if len(set(hs)) != len(hs):
                problems.append(f"{p.get('name')}: two units at the same height — "
                                f"legal on a sidearm, but say which side")
        t = (p.get("type") or "").strip().lower()
        if t in HANGING_TYPES:
            # ⭐ A ladder HANGS. Asking it for a boom base is asking for hardware
            # that does not exist — what it needs is a trim, and §3 requires one
            # for "all hanging positions that can change height."
            if p.get("trim") is None:
                problems.append(f"{p.get('name')}: a ladder hangs, so it needs a TRIM, "
                                f"not a floor mount. RP-2 §3 wants a trim on every "
                                f"position whose height can change")
            if p.get("mount"):
                problems.append(f"{p.get('name')}: a ladder has a mount recorded "
                                f"({p['mount']!r}) but it does not stand on the floor — "
                                f"is this a boom?")
        elif t in FIXED_TYPES:
            # A tormentor is bolted to the building. Nothing to specify, nothing
            # to choose, and no base to bring.
            pass
        elif not p.get("mount"):
            problems.append(f"{p.get('name')}: no mount recorded (floor plate, boom "
                            f"base or flange). A floor plate needs floor space and a "
                            f"sandbag; a flange is already in the building")
    return problems


# ---------------------------------------------------------------------------
# Conventions the standard does not cover.

# RP-2 requires a channel to be SHOWN and says channel hookups are "not
# addressed in this document." So this is Jerry's own, recorded 2026.09.23:
#
#     "How I do channels... the numbers actually go house left to house right —
#      easier to read, and visualize from the house."
#
# House left is stage right, so channel 1 sits at the MAXIMUM x.
CHANNEL_FROM = FROM_SR


def channel_order(instruments):
    """Instruments in Jerry's channel order: house left to house right.

    ⚠ This is the reverse of RP-2's UNIT numbering across the same batten, and
    that is deliberate rather than an inconsistency. A unit number is read by
    someone standing under the pipe with a wrench; a channel number is read by
    someone sitting in the house looking at the plot. They serve different people
    and they are allowed to run different ways.
    """
    return sorted(instruments, key=lambda i: -(i.get("x") or 0.0))


def channel_note():
    """A line for the plot's legend, since the standard does not set this."""
    return ("Channels run house left to house right. (RP-2 sets unit numbering "
            "but does not address channels.)")


def trim_conflicts(plot: Dict[str, Any]) -> List[str]:
    """Where a position's trim and its units' trims disagree.

    🔴 Found 2026.09.24 by editing a trim in the browser and watching nothing
    happen: the label read "GRID C — trim 18'-0"" while every unit on it went on
    computing from 14. Two places held the same fact and only one of them was
    being read, so the drawing could STATE one trim and COMPUTE another.

    A unit hung below its pipe is legal — a sidearm, a drop-arm, a boom head —
    so this reports rather than corrects. But it must report: the silent version
    is a plot whose printed trim is a lie.
    """
    out: List[str] = []
    for p in plot.get("positions") or []:
        trim = p.get("trim")
        if trim is None or is_vertical(p):
            continue
        name = (p.get("name") or "").strip().lower()
        off = [(i.get("unit"), i.get("trim")) for i in plot.get("instruments") or []
               if (i.get("position") or "").strip().lower() == name
               and i.get("trim") is not None
               and abs(float(i["trim"]) - float(trim)) > 0.02]
        if off:
            listed = ", ".join(f"unit {u} at {t}'" for u, t in off[:4])
            more = f" (+{len(off) - 4} more)" if len(off) > 4 else ""
            out.append(f"{p.get('name')} is trimmed at {trim}' but {listed}{more}. "
                       f"Legal on a sidearm — but if the pipe moved, the units did not")
    return out


def apply_trim(plot: Dict[str, Any], position_name: str, trim: float) -> int:
    """Move a position's trim AND every unit on it that was at the old trim.

    Units that were deliberately off the pipe keep their offset — moving a pipe
    should carry the rig with it without flattening a drop-arm.
    """
    name = (position_name or "").strip().lower()
    pos = next((p for p in plot.get("positions") or []
                if (p.get("name") or "").strip().lower() == name), None)
    if pos is None:
        return 0
    old = pos.get("trim")
    pos["trim"] = trim
    if old is None:
        return 0
    moved = 0
    for i in plot.get("instruments") or []:
        if (i.get("position") or "").strip().lower() != name or i.get("trim") is None:
            continue
        i["trim"] = float(i["trim"]) + (trim - old)      # keep any deliberate offset
        moved += 1
    return moved


# A pipe hangs BELOW the grid, and the instrument hangs below the pipe. A
# Source Four on a c-clamp is about 20 inches from the pipe to the lens, and the
# clamp itself wants a couple of inches above. Call it 1'-6" of headroom before
# a trim is physically impossible rather than merely tight.
INSTRUMENT_DROP = 1.5


def horizontal_zero(room: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The drawing's horizontal reference, and what it IS.

    ⭐ RP-2 §3 asks for "proscenium, plaster line, smoke pocket, or the
    'horizontal zero' location" — the standard already knows that not every room
    has a proscenium. Jerry, 2026.09.24: "it's a black box so there's technically
    no plaster line."

    So a plaster line is one KIND of horizontal zero, not the only one. A black
    box declares some other reference — a wall, a grid line — and the drawing
    says which, because a dimension measured from an unnamed origin is a number
    nobody else can use.
    """
    hz = room.get("horizontalZero")
    if isinstance(hz, dict):
        # ⭐ `at: "center"` resolves against the room rather than hard-coding a
        # number. Jerry, 2026.09.24: "our origin could be the centre of the
        # room." In a black box that is the best datum available — the centre is
        # findable in an empty room, whereas a downstage wall is arbitrary when
        # the audience can end up on any side of you.
        #
        # ⚠ It is a DATUM, not the storage origin. Coordinates stay where they
        # are — corner-based, x to stage right, y upstage — because moving them
        # would rewrite every plot on disk to say the same thing differently.
        # What this changes is where dimensions are measured FROM.
        if str(hz.get("at", "")).lower() in ("center", "centre", "middle"):
            depth = room.get("depth")
            if depth is None:
                return None
            return {"y": float(depth) / 2.0,
                    "name": hz.get("name") or "centre of the room"}
        if hz.get("y") is not None:
            return {"y": float(hz["y"]), "name": hz.get("name") or "horizontal zero"}
    pl = room.get("plasterLine")
    if pl is not None:
        return {"y": float(pl), "name": "plaster line"}
    return None


def center_line(room: Dict[str, Any]) -> Optional[float]:
    """The lateral datum — x of the centreline.

    RP-2 §2.3.1 already assumes one: "all hanging locations not intersecting
    centerline are subnamed by their location relative to centerline." It is the
    room's middle unless a room says otherwise.
    """
    cl = room.get("centerLine")
    if cl is not None:
        return float(cl)
    w = room.get("width")
    return float(w) / 2.0 if w is not None else None


def is_foh(pos: Dict[str, Any], plaster_line: Optional[float] = None) -> bool:
    """Front of house — DOWNSTAGE OF THE PLASTER LINE.

    ⚠ Corrected 2026.09.24. This used to mean "negative y", on the assumption
    that `room` was the STAGE and the house lay beyond it. Jerry: "the FOH
    catwalk would need to be inside the room."

    He is right, and in a black box it is obvious once said: **the room is the
    whole room.** The test room is 33' x 38' with its plaster line at y = 10, so the
    house is y 0–10 and the stage is 10–38 — both inside one rectangle. Placing
    an FOH position at negative y put it outside a room that already had space
    for it, and made the drawing invent paper it did not need.

    So FOH is a matter of WHERE a position sits, not of the sign of its y.

    ⚠ And in a BLACK BOX there is no plaster line at all (Jerry, 2026.09.24) —
    no proscenium, so nothing for "downstage of" to mean. What divides house from
    stage there is the SEATING, and the seating moves; at the test room the risers
    are repositioned per production, which is why the configuration is part of
    the design rather than a property of the room. So with no plaster line the
    `foh` flag is the only answer, and it is the DESIGNER'S statement rather than
    something geometry can work out.
    """
    foh = pos.get("foh")
    if foh is not None:
        return bool(foh)
    if plaster_line is None:
        return False
    return float(pos.get("y1", 0.0)) < float(plaster_line)


def headroom(plot: Dict[str, Any]) -> List[str]:
    """Trims checked against the room's ceiling. Returns problems, worst first.

    🔴 Found 2026.09.24 by Jerry: "I guess we need a ceiling height — the ceiling
    is probably closer to 16'." Nothing had been checking. A pipe had just been
    raised to 18' in a room with a 15' grid and the tool drew it, computed
    footcandles from it and printed it, without a word.

    ⚠ It reports rather than clamping. A grid height that came off a rental
    listing is not a measurement, and refusing a designer's trim on the strength
    of a web page would be worse than saying what the page claims.
    """
    out: List[str] = []
    room = plot.get("room") or {}
    grid = room.get("gridHeight")
    if grid is None:
        if any(p.get("trim") is not None for p in plot.get("positions") or []):
            out.append("no ceiling height recorded (room.gridHeight) — trims are "
                       "NOT checked against anything. Measure it at the site visit")
        return out

    src = room.get("gridSource")
    note = f" (grid {grid}': {src})" if src else f" (grid {grid}')"

    house_ceiling = room.get("houseCeiling")
    for p in plot.get("positions") or []:
        trim = p.get("trim")
        if trim is None:
            continue

        # ⚠ A FRONT-OF-HOUSE position hangs from the HOUSE ceiling, not the stage
        # grid, and the house is usually higher — a catwalk over the audience at
        # 18' in a room with a 15' stage grid is ordinary, not impossible.
        # Checking it against the grid reports a fault that is not there, which
        # is worse than not checking: a warning that is wrong teaches the reader
        # to ignore the ones that are right.
        if is_foh(p):
            if house_ceiling is None:
                out.append(f"{p.get('name')} is front of house at {trim}' and no "
                           f"house ceiling is recorded (room.houseCeiling) — not "
                           f"checked. The house is usually higher than the grid")
            elif trim > house_ceiling:
                out.append(f"🔴 {p.get('name')} is at {trim}' — above the HOUSE "
                           f"ceiling ({house_ceiling}')")
            continue

        if trim > grid:
            out.append(f"🔴 {p.get('name')} is trimmed at {trim}' — ABOVE the "
                       f"ceiling{note}. This cannot be hung")
        elif trim > grid - INSTRUMENT_DROP:
            out.append(f"{p.get('name')} at {trim}' leaves under "
                       f"{INSTRUMENT_DROP:.1f}' below the grid{note} — a Source Four "
                       f"and its clamp need about that much. Check it in the room")

    for i in plot.get("instruments") or []:
        h = i.get("height")
        if h is not None and h > grid:
            out.append(f"🔴 unit {i.get('unit')} on {i.get('position')} is at {h}' "
                       f"— above the ceiling{note}")
    return out


def check_foh(plot: Dict[str, Any]) -> List[str]:
    """Where a position's `foh` flag disagrees with where it actually sits.

    ⭐ The flag and the geometry are two statements of the same fact, so they can
    contradict each other — and the contradiction is silent. A position marked
    onstage while sitting downstage of the plaster line is either mislabelled or
    misplaced, and either way the drawing is wrong about which side of the
    proscenium a unit is on.

    Found in this tool's own sample on 2026.09.24: a boom flagged `foh: false`
    at y=9 with the plaster line at y=10.
    """
    out: List[str] = []
    room = plot.get("room") or {}
    hz = horizontal_zero(room)
    pl = hz["y"] if hz and hz["name"] == "plaster line" else None
    depth = room.get("depth")
    if pl is None:
        # No plaster line — a black box. Only the flags can be checked, and a
        # flag cannot contradict a geometry that does not exist.
        for p in plot.get("positions") or []:
            y = p.get("y1")
            if y is not None and depth is not None and not (0 <= float(y) <= float(depth)):
                out.append(f"🔴 {p.get('name')} is at y={y}', OUTSIDE the room "
                           f"(0 to {depth}')")
        return out
    for p in plot.get("positions") or []:
        y = p.get("y1")
        if y is None:
            continue
        geometric = float(y) < float(pl)
        stated = p.get("foh")
        if stated is not None and bool(stated) != geometric:
            where = "downstage" if geometric else "upstage"
            out.append(f"{p.get('name')} is flagged foh={stated} but sits {where} of "
                       f"the plaster line ({y}' against {pl}'). One of the two is wrong")
        if depth is not None and not (0 <= float(y) <= float(depth)):
            out.append(f"🔴 {p.get('name')} is at y={y}', OUTSIDE the room "
                       f"(0 to {depth}'). The room is the whole room — house and "
                       f"stage — so nothing should sit beyond it")
    return out
