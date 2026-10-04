#!/usr/bin/env python3
"""Draw the lighting SECTION from a .plot.json, to RP-2 §3's checklist.

    cd server && python3 plot_to_section.py testdata/blackbox.plot.json ../out/sec.pdf

⭐ A section answers two questions the plan cannot: **how low can this pipe go,
and does the light reach the actor's face.** That is why RP-2 asks for two things
the old section here had neither of —

    "Scaled representation of the luminaire that determines batten height
     mounted in each position."
    "Human figure (or 'head height') in scale."

A unit drawn as a dot cannot show whether it clears the masking; a head-height
line cannot show whether a 30-degree front light hits a face or a forehead.

⚠ AND IT IS ONE LUMINAIRE PER POSITION, not every unit. RP-2 says "the luminaire
that DETERMINES batten height" — the governing one. Drawing all sixty turns the
section into a smear and hides the only thing it is for.
"""
import json
import math
import sys

from plotedit.scaled_pdf import Sheet, ft
from plotedit import photometrics as ph
from plotedit import positions as P
from plotedit import symbols as sym


def governing_unit(units, cut_at, axis="y"):
    """The unit on a position that determines its trim.

    Default: the one nearest the cut plane, because that is the one the section
    actually passes through. A position may name its own with `governing`, since
    which unit constrains a trim is a judgment the designer makes, not arithmetic.
    """
    if not units:
        return None
    named = [u for u in units if u.get("governing")]
    if named:
        return named[0]
    key = "x" if axis == "y" else "y"
    return min(units, key=lambda u: abs((u.get(key) or 0.0) - cut_at))


def _figure(s, x, head_h):
    """A human figure at scale. RP-2 asks for one, and it is not decoration:
    it is the only thing on the sheet that says whether the light lands on a
    face or on the top of a head."""
    from reportlab.lib.colors import grey
    head_r = ft(0, 4)
    s.circle(x, head_h - head_r, head_r, width=0.7, color=grey)
    s.line(x, head_h - 2 * head_r, x, ft(1, 8), width=0.7, color=grey)   # torso
    s.line(x, ft(2, 10), x - ft(0, 7), ft(2, 2), width=0.6, color=grey)  # arms
    s.line(x, ft(2, 10), x + ft(0, 7), ft(2, 2), width=0.6, color=grey)
    s.line(x, ft(1, 8), x - ft(0, 6), 0, width=0.7, color=grey)          # legs
    s.line(x, ft(1, 8), x + ft(0, 6), 0, width=0.7, color=grey)
    s.text(x + ft(0, 10), head_h, f"head height {ph.fmt_ft(head_h)}", size=5.5, color=grey)


def render(plot_path, pdf_path, cut_at=None, axis="y", scale="fit",
           page="ARCH_D", landscape=True, head_h=5.5):
    # "fit" zooms in as far as the sheet allows, on standard scales only. The
    # section is the drawing trims are read off, so a bigger scale is a more
    # useful drawing — as long as nothing falls off the edge.
    if scale in ("fit", "max", None):
        from plotedit.scaled_pdf import largest_scale as _largest
        scale = _largest(lambda k, path: render(plot_path, path, cut_at=cut_at,
                                                axis=axis, scale=k, page=page,
                                                landscape=landscape, head_h=head_h)[0])

    plot = json.load(open(plot_path))
    room = plot["room"]
    depth, width = room["depth"], room["width"]
    grid = room.get("gridHeight") or 16.0

    # §3: "Definition of where the section is cut." Default: on centerline.
    if cut_at is None:
        cut_at = width / 2.0
    cut_desc = ("on centerline" if abs(cut_at - width / 2) < 0.1
                else f"at {ph.fmt_ft(cut_at)} from stage left")

    house = Sheet.foh_extent(plot.get("positions"))
    s = Sheet(pdf_path, page=page, scale=scale, landscape=landscape,
              show=plot["show"], venue=plot.get("venue", ""),
              sheet=f"Section — cut {cut_desc}, looking stage left",
              rev=str(plot.get("revision", "0"))[:3],
              designer=(f"Design: {plot['designer']}" if plot.get("designer") else ""),
              studio=plot.get("studio", ""))
    # ⚠ The left margin has to absorb what is drawn LEFT of the room: the deck
    # runs a foot past it, and the labels run further still. The guard reported
    # 5.4' off the left edge once the sight point moved back inside the room.
    s.origin(ft(9), ft(3))

    s.layer("BASE")
    # §3: the deck, and WHICH zero it is. A section with an unstated reference is
    # a drawing nobody can measure a trim from.
    s.rect(-house - 1, -ft(0, 4), depth + house + 2, ft(0, 4), style="architecture")
    s.text(-house - 1, -ft(1, 2), "STAGE FLOOR = VERTICAL ZERO (±0'-0\")", size=6, bold=True)

    # §3: plaster line = horizontal zero; downstage edge; upstage limit.
    # §3: "proscenium, plaster line, smoke pocket, or the 'horizontal zero'
    # location" — and say WHICH. A black box has no plaster line, so printing one
    # would be drawing a piece of architecture that is not in the building.
    hz = P.horizontal_zero(room)
    if hz is not None:
        s.line(hz["y"], -ft(0, 6), hz["y"], grid + 2, style="plasterline")
        s.text(hz["y"], grid + ft(2, 4),
               f"{hz['name'].upper()} = HORIZONTAL ZERO  (0'-0\")",
               size=6, bold=True, center=True)
        # ⚠ Say where the OTHER references are relative to it, or the reader has
        # to do the arithmetic that the drawing exists to save them.
        for edge, label in ((0.0, "DS EDGE"), (depth, "US LIMIT")):
            off = edge - hz["y"]
            s.text(edge, grid + ft(0, 10),
                   f"{'+' if off >= 0 else ''}{ph.fmt_ft(off)}", size=5, center=True)
    else:
        s.note(1, grid + 3.8, "No horizontal zero declared (room.horizontalZero) — "
                              "dimensions on this drawing have no stated origin.")
    s.line(0, -ft(0, 6), 0, grid + 1, style="centerline")
    s.text(0, grid + ft(1, 4), "DS EDGE", size=5.5, center=True)
    s.line(depth, -ft(0, 6), depth, grid + 1, style="centerline")
    s.text(depth, grid + ft(1, 4), "US LIMIT", size=5.5, center=True)

    # §3: vertical sightline from a stated audience eye point.
    sp = room.get("sightPoint")     # {"y": ft from DS edge (negative = house), "h": eye height}
    if sp:
        s.layer("NOTES")
        s.line(sp["y"], sp.get("h", 3.5), depth, grid, style="leader")
        s.text(sp["y"], sp.get("h", 3.5) + ft(0, 6),
               f"sight point {ph.fmt_ft(abs(sp['y']))} into house, eye {ph.fmt_ft(sp.get('h', 3.5))}",
               size=5.5)

    # ⭐ One block, listing what is NOT on this drawing and who has it.
    #
    # A warning that cannot be acted on is just noise on a sheet. These are
    # things the designer does not have YET — so the drawing states the gap, says
    # who to ask, and says what the drawing cannot be used to prove until it is
    # filled. That is a site-visit list, not a nag.
    missing = []
    if not sp:
        missing.append(("Audience sight point", "the venue — the worst seat's row and eye height",
                        "no vertical sightline is drawn; sightlines are NOT checked"))
    if not plot.get("masking"):
        missing.append(("Masking — borders, legs, teasers", "the venue's rep plot or its TD",
                        "trims are NOT proven to clear; a pipe may hang into a border"))
    if not plot.get("scenery"):
        missing.append(("Scenery in section", "the set designer",
                        "no obstruction is checked; a beam may be blocked"))
    if missing:
        s.layer("NOTES")
        # Placed over MID-STAGE and well above the grid. The obvious spot — top
        # left — is where the FOH positions live, because a catwalk is at
        # negative y and its trim is above the grid. The empty corner of a
        # section is not empty once the house is drawn.
        bx = depth * 0.22
        by = grid + 10.0
        s.text(bx, by, "NOT ON THIS DRAWING — and what it means", size=7.5, bold=True)
        for what, who, means in missing:
            by -= 1.05
            s.text(bx, by, f"{what} — ask {who}.", size=5.5)
            by -= 0.65
            s.text(bx + 0.6, by, f"Until then: {means}.", size=5.5)
        by -= 1.15
        s.text(bx, by,
               "This section shows the ROOM AND THE RIG. It is not a clearance check.",
               size=6.5, bold=True)

    s.layer("POSITIONS")
    insts = plot["instruments"]
    drawn = []
    for pos in plot.get("positions", []):
        name = (pos.get("name") or "").strip().lower()
        on = [i for i in insts if (i.get("position") or "").strip().lower() == name]
        here = pos["y1"] if axis == "y" else pos["x1"]

        if P.is_vertical(pos):
            # §3: "all hanging positions including side elevation of booms,
            # ladders, etc." A boom IS its side elevation here — the one view
            # where it is not a point.
            top = max([u.get("height") or 0 for u in on] or [grid]) + 1
            s.line(here, 0, here, top, style="batten")
            s.text(here, top + ft(0, 6), (pos.get("name") or "").upper(),
                   size=6, bold=True, center=True)
            for u in on:
                h = u.get("height")
                if h is None:
                    continue
                prims = sym.for_type(u.get("type", ""))
                sym.draw(s, prims, here, h, rotate_deg=90, width=1.0)
                s.text(here - sym.radius(prims) - ft(0, 3), h, ph.fmt_ft(h),
                       size=5, align="right")
            continue

        trim = pos.get("trim")
        if trim is None:
            continue
        s.line(here - ft(0, 4), trim, here + ft(0, 4), trim, style="batten")

        # ⭐ §3: the scaled luminaire that determines the batten height. ONE.
        u = governing_unit(on, cut_at, axis)
        # Clear the labels by the SYMBOL's radius, not by a guess — the same
        # collision the plan had, for the same reason: symbols are not one size.
        clear = (sym.radius(sym.for_type(u.get("type", ""))) if u else 0.0) + ft(0, 4)
        s.text(here, trim + clear + ft(0, 6), (pos.get("name") or "").upper(),
               size=6, bold=True, center=True)
        s.text(here, trim + clear, f"TRIM {ph.fmt_ft(trim)}", size=5.5, center=True)
        if not u:
            continue
        fx = u.get("focusX"); fy = u.get("focusY")
        elev = 0.0
        if fx is not None and fy is not None:
            a = ph.aim((u["x"], u["y"], trim), (fx, fy, head_h))
            elev = a["elevation"]
            target = fy if axis == "y" else fx
            # ⚠ Point the symbol along the REAL direction in the cut plane, not
            # at an angle derived from the elevation. The elevation is unsigned,
            # so 40° describes both "down and upstage" and "down and downstage"
            # — deriving a rotation from it aims half the rig the wrong way, and
            # a section whose instruments point somewhere they do not is worse
            # than no section.
            #
            # symbols.draw() takes 0° as pointing toward -y (straight down here),
            # measured counter-clockwise, so the offset is +90 from the standard
            # atan2 angle.
            rot = math.degrees(math.atan2(head_h - trim, target - here)) + 90
            sym.draw(s, sym.for_type(u.get("type", "")), here, trim, rotate_deg=rot, width=1.0)
            s.layer("NOTES")
            s.line(here, trim, target, head_h, style="leader")
            key, row, _ = ph.lookup(u.get("type"))
            if row and row.get("field"):
                half = math.radians(row["field"]) / 2
                e = math.radians(elev)
                d = 1 if target >= here else -1
                for ang in (e - half, e + half):
                    if ang <= 0.02:
                        continue
                    end = here + d * trim / math.tan(ang)
                    # 🔴 CLIPPED TO THE DRAWN ROOM. A beam edge is projected to the
                    # floor, and a SHALLOW one lands a very long way off: the
                    # guard above only skips angles under 0.02 rad — 1.1° — so a
                    # 2° edge from a 14' trim ran out to roughly 400 feet.
                    #
                    # ⚠ ONE such line stretched the whole drawing's extent to 93
                    # feet for a 38-foot room, which pushed `fit` down a scale
                    # step and left the section using 17% of an ARCH D sheet.
                    # Found by exporting one and looking at it (#92).
                    #
                    # The segment is clipped rather than dropped, because the
                    # near part of the edge is real and worth drawing — it is
                    # only the far tail that is off the paper and meaningless.
                    lo, hi = -house - 1, depth + house + 1
                    ex, ey = end, 0.0
                    if ex < lo or ex > hi:
                        bound = lo if ex < lo else hi
                        t = (bound - here) / (end - here) if end != here else 0.0
                        ex, ey = bound, trim + t * (0.0 - trim)
                    s.line(here, trim, ex, ey, style="pool")
            s.text(target, -ft(1, 10),
                   f"{u.get('type')} · {ph.fmt_ft(a['throw'])} @ {elev:.0f}°",
                   size=5, center=True)
            s.layer("POSITIONS")
        else:
            sym.draw(s, sym.for_type(u.get("type", "")), here, trim, rotate_deg=90, width=1.0)
        drawn.append((pos.get("name"), u.get("unit"), u.get("type")))

    # §3: a human figure, in scale.
    s.layer("NOTES")
    _figure(s, depth * 0.45, head_h)

    s.note(1, grid + 1.6,
           "One luminaire per position — the unit that determines the batten height "
           "(RP-2 §3). Others on the same pipe are not drawn.")
    s.finish()
    return s, drawn


if __name__ == "__main__":
    args = sys.argv[1:]
    s, drawn = render(args[0] if args else "testdata/blackbox.plot.json",
                      args[1] if len(args) > 1 else "../out/section.pdf")
    for w in s.warnings:
        print("⚠", w)
    print(f"{len(drawn)} positions drawn, one governing luminaire each:")
    for name, unit, kind in drawn:
        print(f"   {name:24s} unit {unit}  {kind}")
