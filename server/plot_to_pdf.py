#!/usr/bin/env python3
"""Render a .plot.json through scaled_pdf — the same file the browser draws.

    cd server && python3 plot_to_pdf.py testdata/blackbox.plot.json ../out/blackbox.pdf

This is step 3's proof: the screen and the paper must agree. It is also the
beginning of step 5's export, so it lives in the package rather than in a test.
"""
import json
import os
import sys

from plotedit.scaled_pdf import Sheet, ft, check, largest_scale, FIT_SCALES
from plotedit import photometrics as ph


# ⚠ The pitch and the placement live in booms.py, with the compression, so the
# browser draws the elevations in the same places the paper does.
from plotedit.booms import BOOM_PITCH


def render(plot_path, pdf_path, scale="fit", page="ARCH_D", landscape=True, dxf=None,
           pool_plane=None, show_pools=True, show_focus=True, show_labels=True,
           rulers=None, lift=None):
    """Draw the plot.

    ⭐ `lift` is how far up the sheet the drawing sits, in feet, and None means
    WORK IT OUT. The origin below pads for the FOH catwalk and the boom
    elevations so neither is clipped off the bottom or the left — it is a FLOOR,
    and nothing ever asked what was left over above, so every spare inch landed
    at the top. Measured 2026.09.30 on Jerry's own exports: 31% of the height
    wasted on Letter, 38% on ARCH C, 47% on TABLOID, always with the bare 0.5"
    margin below.

    ⚠ It takes two passes because the extent is not knowable in advance — booms,
    key, labels and the title block all contribute, and the title block is drawn
    last. The sheet already tracks what it drew for the clipping guard, so pass
    one measures and pass two draws. The fit search above already renders
    repeatedly for the same reason.
    """
    from plotedit import units as _units
    # "fit" means: zoom in as far as the sheet allows. An explicit scale is
    # still honoured — a plot issued at 1/4" stays at 1/4" when it is reissued.
    # ⚠ The system has to be known BEFORE the fit search, because the ladder it
    # climbs is different: imperial fractions or metric ratios. Read straight
    # from the file rather than waiting for the Sheet, which does not exist yet.
    import json as _json
    _system = _units.system_of(_json.load(open(plot_path)))
    if scale in ("fit", "max", None):
        # ⚠ The fit search has to draw the SAME picture that will be issued.
        # Pools are the widest thing on a plot by a distance, so measuring with
        # them on and then issuing with them off picks a scale far smaller than
        # the sheet can hold — a drawing correct in every dimension and half the
        # size it should be.
        # ⚠ lift=0 through the search. Centring only ever happens on a drawing
        # that ALREADY FITS (see below), so it cannot change which scale fits —
        # and letting each trial run its own two passes would double the work of
        # a search that already renders the plot six times.
        scale = largest_scale(
            lambda k, path: render(plot_path, path, scale=k, page=page,
                                   landscape=landscape, pool_plane=pool_plane,
                                   show_pools=show_pools, show_focus=show_focus,
                                   show_labels=show_labels, rulers=rulers,
                                   lift=0.0)[0],
            system=_system)

    # ⭐ PASS ONE: draw it at the floor to find out how much room is left.
    if lift is None:
        import tempfile as _tf
        with _tf.TemporaryDirectory() as _d:
            _probe, _ = render(plot_path, os.path.join(_d, "probe.pdf"),
                               scale=scale, page=page, landscape=landscape,
                               dxf=dxf, pool_plane=pool_plane,
                               show_pools=show_pools, show_focus=show_focus,
                               show_labels=show_labels, rulers=rulers, lift=0.0)
        lift = _probe.slack_above()

    plot = json.load(open(plot_path))
    room = plot["room"]
    s = Sheet(pdf_path, page=page, scale=scale, landscape=landscape,
              show=plot["show"], venue=plot.get("venue", ""),
              sheet=plot.get("revision", ""), rev=plot.get("revision", "0")[:3],
              designer=(f"Design: {plot['designer']}" if plot.get("designer") else ""),
              studio=plot.get("studio", ""), dxf=dxf,
              # ⭐ Line weights come off the PLOT, not off an export option.
              # "the pipes are too thick" is a property of the drawing, so it
              # belongs with the drawing and travels with the file.
              weights=plot.get("lineWeights"),
              units=_units.system_of(plot))
    # ⭐ FOH positions — catwalks — sit over the AUDIENCE, downstage of the
    # plaster line and outside the stage rectangle, at negative y. The origin has
    # to make room for them or they are clipped straight off the bottom of the
    # sheet and only the clipping guard would ever say so.
    house = Sheet.foh_extent(plot.get("positions"))

    # The boom elevations sit off the stage-left edge at negative x, so the
    # origin has to make room for them too — the same failure as the catwalk,
    # in the other axis. Counted BEFORE the origin is set, not discovered by the
    # clipping guard afterwards.
    from plotedit import booms as _B
    boom_space = _B.space_needed(plot["positions"], plot["instruments"])
    _floor_y = ft(4) + (house + 1.5 if house else 0)
    s.origin(ft(4) + boom_space, _floor_y + (lift or 0.0))

    s.layer("BASE")
    # §6.18: architecture is HEAVY; the reference lines are MEDIUM and dashed;
    # dimensions are LIGHT.
    s.rect(0, 0, room["width"], room["depth"], style="architecture")
    s.center_line(room["width"] / 2, -1.0, room["depth"] + 1.0)
    if room.get("plasterLine") is not None:
        s.plaster_line(room["plasterLine"], -1.0, room["width"] + 1.0)
    s.dim(0, -1.5, room["width"], -1.5)
    s.dim(-1.5, 0, -1.5, room["depth"])

    from plotedit import positions as P
    from plotedit import labels as L
    booms = [p for p in plot["positions"] if P.is_vertical(p)]

    # ⭐ Fit every position NAME before drawing any of them, around the units and
    # around each other. Placed one at a time at the pipe's stage-left end, CAT 1
    # and HOUSE LEFT BOX BOOM 1 landed on top of each other AND on the box
    # boom's symbol — three marks in one place, the important one underneath.
    # The browser asks POST /labels for the same slots.
    def _measure(text, _c=s.c, _p=s.pt_per_ft):
        return _c.stringWidth(text, "Helvetica-Bold", 7) / _p

    # ⚠ The drawable area, in plot feet. Without it the fitter is free to move a
    # name to the far end of a pipe to dodge a symbol and put it off the edge of
    # the sheet — trading a collision for a position with no name at all, which
    # is the worse of the two.
    _W, _H = s.page_pt
    _bounds = (-(s.ox - s.margin) / s.pt_per_ft,
               -(s.oy - s.margin) / s.pt_per_ft,
               (_W - s.margin - s.ox) / s.pt_per_ft,
               (_H - s.margin - s.oy) / s.pt_per_ft)

    spots = {id(p): a for p, a in
             zip(plot["positions"],
                 L.plan(plot["positions"], plot["instruments"], _measure,
                        room_width=room["width"], system=_system, bounds=_bounds))}

    for p in plot["positions"]:
        at = spots.get(id(p))
        if P.is_vertical(p):
            on = [i for i in plot["instruments"]
                  if (i.get("position") or "").strip().lower() == (p.get("name") or "").strip().lower()]
            s.boom(p, units=on, center_x=room['width'] / 2,
                   label=at["text"] if at else None, label_at=at)
            continue
        # ⚠ Trim on the plan only where the position can MOVE. RP-2 §2.1 asks
        # for "trim measurements for MOVABLE mounting positions" — a dead-hung
        # grid pipe is not one, and a number that cannot change is clutter on
        # every pipe in the room. The SECTION carries trim for everything.
        # (Jerry, 2026.09.24.) labels.text_for() assembles it, so the screen and
        # the paper cannot disagree about what a pipe is called.
        s.position(p, label=at["text"] if at else p["name"], label_at=at)

    # §6.12: the readable layout goes BESIDE the plot, because in plan a boom is
    # a point. Placed off the room's stage-left edge, which is the low-x side.
    _placed = {b["name"]: b for b in _B.layout(plot["positions"], plot["instruments"], system=_system)}
    # 🔴 ONE FOOTNOTE FOR THE STRIP, not one per boom. Each elevation used to
    # draw "NOT TO SCALE — heights are the data" centred on its own pipe, so two
    # booms standing near each other overprinted the sentence and neither copy
    # was readable. Found on a tester's export, 2026.09.30.
    _drawn = []
    for p in booms:
        spot = _placed.get((p.get("name") or "").upper())
        if spot:
            _, _cuts = s.boom_elevation(
                p, _B.units_on(p, plot["instruments"]), spot["x"], spot["y"],
                layout=p.get("layout") or plot.get("boomLayout", "option1"),
                note=False)
            _drawn.append((spot["x"], spot["y"], _cuts))
    if _drawn:
        s.boom_note(min(d[0] for d in _drawn), max(d[0] for d in _drawn),
                    min(d[1] for d in _drawn),
                    compressed=sum(1 for d in _drawn if d[2]), total=len(_drawn))

    # ⭐ A unit on a BOOM is drawn in its elevation, not in plan — see
    # Sheet.unit(in_plan=...). Its focus and its pool are still drawn here.
    _boom_names = {(p.get("name") or "").strip().lower()
                   for p in plot["positions"] if P.is_vertical(p)}

    # 🔴 Colour labels that would touch get pushed further out (issue #21). The
    # text is 7pt on paper, so how much of the STAGE it covers depends on the
    # scale — at 1/4" nothing on the demo plot collides, at 1/8" it does. Work
    # the tiers out once, here, where the scale is known.
    _text_h = 7.0 / s.pt_per_ft if getattr(s, "pt_per_ft", None) else 0.39
    _tiers = L.color_tiers(plot["instruments"], _text_h)

    rows = []
    for _i, inst in enumerate(plot["instruments"]):
        focus = ((inst["focusX"], inst["focusY"])
                 if inst.get("focusX") is not None else None)
        r = s.unit(inst["x"], inst["y"], inst["unit"], ch=inst.get("channel"),
                   kind=inst["type"], color_gel=inst.get("color"),
                   trim=inst.get("trim"), focus_to=focus,
                   focus_h=inst.get("focusH", 5.5), lamp=inst.get("lamp"),
                   mode=inst.get("mode"),
                   lens_rotation=inst.get("lensRotation"),
                   accessories=inst.get("accessories"),
                   circuit=inst.get("circuit"), dimmer=inst.get("dimmer"),
                   address=inst.get("address"),
                   control=plot.get("control", "dimmer-per-circuit"),
                   wattage=inst.get("wattage"),
                   symbol_angle=plot.get("symbolAngle", "orthogonal"),
                   pool_plane=pool_plane if pool_plane is not None
                              else plot.get("poolPlane"),
                   show_pool=show_pools, show_focus=show_focus,
                   show_labels=show_labels,
                   in_plan=(inst.get("position") or "").strip().lower()
                           not in _boom_names,
                   color_tier=_tiers[_i])
        rows.append(r)

    # ⭐ The key goes ON THE PLOT. §5.0 allows it "in any location that does not
    # conflict with other information", and on the plot is the location that
    # matters: it is the sheet an electrician has in front of them. A key on its
    # own page is a page nobody carries up the ladder.
    from plotedit import key as _key
    _key.draw(s, plot, room["width"] + 4.0, room["depth"])

    # ⭐ The rulers go on LAST, so the tick interval is chosen against the scale
    # that was actually settled on — including the one the fit search picked.
    # Drawn before the origin was known, they would be laid out for a sheet
    # nobody ended up issuing.
    _r = rulers if rulers is not None else plot.get("rulers")
    if _r:
        _opt = _r if isinstance(_r, dict) else {}
        s.rulers(0.0, room["width"], 0.0, room["depth"],
                 step=_opt.get("step"),
                 bottom=_opt.get("bottom", True),
                 side=_opt.get("side", "left"))

    # 🔴 THE ROOM SOURCE IS NO LONGER PRINTED ON THE PLOT (Jerry, 2026.09.30:
    # "lets lose the room site visit stuff"). It was drawn inside the room at
    # depth - 1.5, which is where a pipe label lives — on his own export
    # "Room: Site visit 08-29-2026" sat across "ELECTRIC 7" and neither read.
    #
    # ⚠ IT IS STILL IN THE FILE. `room.source` is data and travels with the
    # plot; what changed is that the sheet stops carrying it. Anything that
    # needs the provenance reads the .plot.json, where it was always the
    # authority — the note was a copy of it.
    #
    # ⚠ AND ONE THING WENT WITH IT. server/testdata/blackbox.plot.json carries
    # "NOT MEASURED and not a real room, so nothing here may be quoted" in that
    # field, so a PDF rendered from the fixture used to say on its face that its
    # dimensions were invented. It no longer does. If that warning is wanted
    # back it belongs in the title block, not across a pipe.
    s.finish()
    return s, rows


if __name__ == "__main__":
    plot_path = sys.argv[1] if len(sys.argv) > 1 else "testdata/blackbox.plot.json"
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else "../out/blackbox.pdf"
    s, rows = render(plot_path, pdf_path)
    print(f"wrote {pdf_path}")
    check(pdf_path)
    if s.warnings:
        for w in s.warnings:
            print("⚠", w)
    print(f"\n{'unit':<5} {'ch':<4} {'type':<15} {'throw':<9} {'pool':<9} {'fc':>6}")
    for r in rows:
        if not r or r.get("throw") is None:
            continue
        fc = f"{round(r['fc'])}" if r.get("fc") else "—"
        print(f"{r['num']:<5} {str(r.get('ch') or ''):<4} {r['kind']:<15} "
              f"{s.fmt_len(r['throw']):<9} {s.fmt_len(r.get('field')):<9} {fc:>6}")
