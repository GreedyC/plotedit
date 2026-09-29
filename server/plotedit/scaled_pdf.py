#!/usr/bin/env python3
"""
scaled_pdf.py — draw theatre paperwork to architectural scale, as PDF.

Amy's drawing tool. ReportLab writes in PostScript points (72 pt = 1 inch
exactly), so a drawing made here measures true on paper — provided it is
printed at 100% / "Actual size", never "Fit to page".

Real-world input is FEET. Convert with ft(feet, inches=0).

    from plotedit.scaled_pdf import Sheet, ft
    s = Sheet("plan.pdf", page="ARCH_D", scale="1/4", landscape=True,
              show="The Test Show", venue="Black Box Studio",
              sheet="Light Plot — plan", rev="A")
    s.origin(ft(2), ft(2))                    # where real-world (0,0) sits on the page
    s.rect(0, 0, ft(33), ft(38), label="Stage floor 33' x 38'")
    s.pipe(0, ft(10), ft(33), label="Pipe 1 — trim 14'")
    s.unit(ft(5), ft(10), 1, ch=1, kind="S4 26")
    s.dim(0, -ft(1), ft(33), -ft(1))          # a dimension line
    s.finish()                                # adds scale bar, 1-inch check, title block

Scales: "1/8", "1/4", "3/8", "1/2", "3/4", "1" (inches on paper per foot),
or any float (paper inches per real foot). Pages: LETTER, LEGAL, TABLOID
(11x17), ARCH_A..ARCH_E, A4, A3. Custom: page=(w_in, h_in).

DXF: pass dxf="plan.dxf" to also write the geometry in feet, layered. Read a
venue's drawing under the plot with s.import_dxf(path, layers=[...], units="in").
Run dxf_bridge.dxf_info(path) first to see its units and layers.

Verify a PDF you did not make here: measure the scale bar with any PDF
reader's measuring tool, or run  scaled_pdf.py --check file.pdf  which
reads the 1-inch check bar and reports its width in points (want 72.0).
"""
import sys, math
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, grey, white, HexColor

PAGES = {  # inches, portrait
    "LETTER": (8.5, 11), "LEGAL": (8.5, 14), "TABLOID": (11, 17),
    "ARCH_A": (9, 12), "ARCH_B": (12, 18), "ARCH_C": (18, 24),
    "ARCH_D": (24, 36), "ARCH_E": (36, 48),
    "A4": (8.27, 11.69), "A3": (11.69, 16.54),
}
SCALES = {"1/8": 0.125, "1/4": 0.25, "3/8": 0.375, "1/2": 0.5, "3/4": 0.75, "1": 1.0}
GREEN, BROWN = HexColor("#256948"), HexColor("#994C00")   # Twin Oaks palette

# ---------------------------------------------------------------------------
# §6.18 LINE WEIGHTS — three, and only three.
#
# RP-2 assigns every element on a plot to one of three weights, and four of the
# medium ones to a dash pattern. Drawing everything at one weight is legible but
# it throws away information an electrician reads without thinking: the heavy
# lines are the things that are physically there — battens, luminaires, walls —
# and the light ones are notation about them.
#
# Widths are in points at final print size, so they are the same on paper
# whatever the drawing scale. Dashes are in points for the same reason.
LIGHT, MEDIUM, HEAVY = 0.5, 0.9, 1.7

LINE_STYLES = {
    # lightweight — notation
    "scenery":      (LIGHT, None),
    "leader":       (LIGHT, (4, 3)),
    "dimension":    (LIGHT, None),
    "pool":         (LIGHT, (2.5, 2)),      # beam pools: our own, not in RP-2
    "grid":         (LIGHT, None),
    # medium — soft goods and reference lines
    "masking":      (MEDIUM, None),
    "drop":         (MEDIUM, (8, 4)),
    "centerline":   (MEDIUM, (11, 3, 2.5, 3)),   # chain-dash
    "plasterline":  (MEDIUM, (5, 4)),
    # heavy — the things that physically exist
    "batten":       (HEAVY, None),
    "luminaire":    (HEAVY, None),
    "architecture": (HEAVY, None),
    "border":       (HEAVY, None),
    "titleblock":   (HEAVY, None),
}


# ⭐ Which line a POSITION is drawn with. Everything physical is heavy under
# RP-2, so an electric and a boom come out identically — which is right by the
# standard and is exactly what makes a plot of thin pipes look heavy. Naming
# them separately is what lets one be made finer than another without moving
# either off the heavy weight.
POSITION_STYLES = {
    "electric": "batten", "pipe": "batten", "grid": "batten",
    "boom": "batten", "box-boom": "batten", "ladder": "batten",
    "catwalk": "architecture", "truss": "batten",
}


def resolve_styles(weights=None):
    """LINE_STYLES with a plot's overrides applied. Returns a NEW dict — the
    module table is the standard and is never mutated.

    `weights` comes straight off the plot file and may carry:

        {"light": 0.4, "medium": 0.8, "heavy": 1.2,   # the three RP-2 weights
         "styles":    {"batten": 1.0},                # one named category
         "positions": {"boom": 0.8}}                  # one position type

    ⚠ Only the WIDTH is overridable. The dash patterns carry meaning — a
    chain-dash IS the centre line — and a plot that redefined them would no
    longer be readable by anyone but its author.
    """
    table = dict(LINE_STYLES)
    if not weights:
        return table
    named = {"light": LIGHT, "medium": MEDIUM, "heavy": HEAVY}
    scale = {k: float(weights[k]) for k in named if weights.get(k) is not None}
    if scale:
        for key, (w, dash) in list(table.items()):
            for name, default in named.items():
                # Float equality is safe here: these widths are the module
                # constants themselves, not arithmetic on them.
                if w == default and name in scale:
                    table[key] = (scale[name], dash)
    for key, w in (weights.get("styles") or {}).items():
        if key not in table:
            raise KeyError(f"{key!r} is not an RP-2 line category; "
                           f"have {sorted(LINE_STYLES)}")
        table[key] = (float(w), table[key][1])
    return table


def style(name):
    """(width, dash) for an RP-2 line category. Raises rather than guessing.

    ⚠ Module-level, so it knows nothing about a plot's overrides. Drawing code
    wants Sheet.style() instead; this stays for callers reading the standard.
    """
    try:
        return LINE_STYLES[name]
    except KeyError:
        raise KeyError(f"{name!r} is not an RP-2 line category; "
                       f"have {sorted(LINE_STYLES)}") from None

def _feet_label(v):
    """A ruler tick, in feet and inches, short enough to sit under a tick.

    Whole feet print as 12'; anything else carries the inches. Negative values
    keep their sign — stage left of a centre-of-room datum IS negative, and
    printing it unsigned would put two different places at the same number.
    """
    sign = "-" if v < 0 else ""
    a = abs(v)
    whole = int(a)
    inches = round((a - whole) * 12)
    if inches == 12:
        whole, inches = whole + 1, 0
    return f"{sign}{whole}'" if inches == 0 else f"{sign}{whole}'-{inches}\""


def ft(feet, inches=0):
    """Real-world length in feet (decimal). ft(12, 6) == 12.5"""
    return feet + inches / 12.0


class Sheet:
    def __init__(self, path, page="ARCH_D", scale="1/4", landscape=True,
                 show="", venue="", sheet="", rev="A", designer="", studio="",
                 margin_in=0.5, dxf=None, weights=None, units=None):
        w, h = PAGES[page] if isinstance(page, str) else page
        if landscape: w, h = h, w
        self.page_pt = (w * inch, h * inch)
        # ⚠ Remember WHICH sheet. The clipping guard could only say "the sheet
        # holds 40.0' x 58.8'" and leave the reader to work backwards from two
        # numbers to a paper size — Jerry, 2026.09.24: "do we know what size
        # sheet it is referring to?" It did not, because nothing kept the name.
        self.page_name = page if isinstance(page, str) else "custom"
        self.landscape = bool(landscape)
        self.page_in = (w, h)
        self.c = canvas.Canvas(path, pagesize=self.page_pt)
        self.path = path
        # ⭐ BOTH SYSTEMS REDUCE TO POINTS PER FOOT, which is why one number runs
        # the whole drawing. 1/4" = 1'-0" IS 1:48 exactly — a foot is twelve
        # inches and a quarter inch goes into twelve forty-eight times — so a
        # metric ratio is not a conversion of an imperial scale, it is the same
        # quantity written the other way.
        #
        # ⚠ The SCALE STRING decides how it is written, not the plot's units. A
        # sheet drawn at "1:50" says 1:50 whoever asked for it, and one drawn at
        # "1/4" says 1/4" = 1'-0". Reading the label off plot.units instead would
        # let a plot claim a ratio it was not drawn at.
        from . import units as _u
        self.is_metric_scale = isinstance(scale, str) and scale.startswith("1:")
        self.pt_per_ft = _u.points_per_foot(scale)         # the whole trick
        self.paper_in_per_ft = self.pt_per_ft / inch
        self.scale_label = (str(scale) if self.is_metric_scale
                            else f'{scale}" = 1\'-0"')
        self.margin = margin_in * inch
        self.ox, self.oy = self.margin, self.margin           # page pt where real (0,0) sits
        # 🔴 NOTHING ABOUT WHOSE DRAWING THIS IS IS HARDCODED. Jerry, 2026.09.24:
        # "I don't want to print anything that is hardcoded about the venue
        # because it will be used for other venues — if we want print from the
        # json, that's cool."
        #
        # The designer defaulted to "Design: Jerry Jonas" and the footer said
        # "Twin Oaks Studios" in the source, so a plot drawn for anyone else
        # came out with his name on it — in the title block, in brown, as a
        # claim of authorship. Both now come from the plot file or stay blank.
        self.meta = dict(show=show, venue=venue, sheet=sheet, rev=rev,
                         designer=designer, studio=studio)
        self.c.setLineJoin(1); self.c.setLineCap(1)
        self._bounds = [1e9, 1e9, -1e9, -1e9]   # page-pt extents of everything drawn
        self.warnings = []
        # ⭐ Resolved ONCE, per sheet. Every drawing call reads self.styles, so
        # an override reaches the whole drawing rather than the handful of
        # places somebody remembered to thread it through.
        self._weights = dict(weights or {})
        self.styles = resolve_styles(weights)
        # ⭐ Which system this sheet PRINTS in. The drawing is still built in
        # FEET — every coordinate, throw and trim below is feet — and this is
        # consulted only where a number becomes text a person reads. Converting
        # any earlier would mean two sets of arithmetic to keep in step, and
        # the one that drifted would be the one nobody was looking at.
        from . import units as _units
        self.unit_system = units or _units.IMPERIAL
        self.base_note = None
        self.dxf_path = dxf
        self.dxf = None
        if dxf:
            from .dxf_bridge import DxfOut
            self.dxf = DxfOut()

    # ---- coordinates -------------------------------------------------
    def origin(self, x_ft, y_ft):
        """Place real-world (0,0) at this many feet in from the page's lower-left margin."""
        self.ox = self.margin + x_ft * self.pt_per_ft
        self.oy = self.margin + y_ft * self.pt_per_ft

    def import_dxf(self, path, **kw):
        """Draw a venue's DXF under the plot as the base drawing. See dxf_bridge.import_into."""
        from .dxf_bridge import import_into
        if self.dxf: self.dxf.layer = "BASE"
        ext = import_into(self, path, **kw)
        if self.dxf: self.dxf.layer = "POSITIONS"
        return ext

    def layer(self, name):
        """Set the DXF layer for what is drawn next (BASE, POSITIONS, UNITS, TEXT, DIMS, NOTES)."""
        if self.dxf: self.dxf.layer = name

    def P(self, x_ft, y_ft):
        """Real feet -> page points. Records extents so finish() can warn about clipping."""
        px, py = self.ox + x_ft * self.pt_per_ft, self.oy + y_ft * self.pt_per_ft
        b = self._bounds
        b[0], b[1], b[2], b[3] = min(b[0], px), min(b[1], py), max(b[2], px), max(b[3], py)
        return px, py

    def L(self, feet):
        return feet * self.pt_per_ft

    # ---- primitives (all args in real feet) --------------------------
    def scale_bar_plan(self, target_in=3.5):
        """(divisions, points per division, total points) for the scale bar.

        🔴 THE BAR IS SIZED TO THE PAPER, not to a fixed count of divisions. It
        used to be ten of them, always — which is five inches of bar at 1/2" and
        ten inches at 1". Metric made that break: a metre at 1:25 is 113pt, so
        ten of them is fifteen and three quarter INCHES of bar. It ran through
        the title block and off the right-hand edge of the sheet, and the "10 m"
        label was not on the page at all.

        ⚠ And nothing caught it, because the bar is drawn in page points
        directly rather than through P() — so the clipping guard, which only
        knows what the DRAWING touched, never saw it leave.

        Divisions come off a round ladder so the numbers under the ticks stay
        readable: 1, 2, 5, 10, 20, 50.
        """
        unit = self.scale_bar_step()
        target = target_in * inch
        # ⚠ At least TWO divisions. One is not a scale bar — the alternating
        # fill is what makes it readable, and a single block has nothing to
        # alternate with. At 1:10 a whole metre is already near the target, so
        # the bar drops to half-metre divisions rather than to one of them.
        best = None
        for per_div, count in ((1.0, 50), (1.0, 20), (1.0, 10), (1.0, 5),
                               (1.0, 2), (0.5, 2)):
            if count * per_div * unit <= target:
                best = (per_div, count)
                break
        if best is None:
            best = (0.5, 2)
        per_div, count = best
        step = per_div * unit
        return count, step, count * step, per_div

    def scale_bar_step(self):
        """Points of paper for ONE division of the scale bar — a foot on an
        imperial sheet, a metre on a metric one.

        ⚠ Its own method so it can be asserted directly. Tested through the
        drawn LABELS alone, a bar ticked "0 5 10 m" with one-foot divisions
        passes: the text is right and the geometry is 3.28 times too short,
        which is the one error on the sheet somebody would measure against.
        """
        from . import units as _u
        return self.pt_per_ft * (_u.FOOT_PER_M if self.is_metric_scale else 1.0)

    def fmt_len(self, value_ft):
        """A length, in the system this sheet prints in. Takes FEET always."""
        from . import units as _units
        return _units.fmt_length(value_ft, self.unit_system)

    def fmt_lux(self, fc):
        """An illuminance, labelled fc or lx to match. Takes FOOTCANDLES always.

        🔴 The label travels with the number. A lux figure printed as "179 fc"
        is a false statement that looks authoritative."""
        from . import units as _units
        return _units.fmt_illuminance(fc, self.unit_system)

    def style(self, name):
        """(width, dash) for an RP-2 category, with this plot's overrides applied.

        ⚠ Not the module-level style(). That one reports the STANDARD; this one
        reports what will actually be drawn on this sheet."""
        try:
            return self.styles[name]
        except KeyError:
            raise KeyError(f"{name!r} is not an RP-2 line category; "
                           f"have {sorted(self.styles)}") from None

    def position_line(self, kind):
        """(style_name, width_override_or_None) for a hanging position.

        ⭐ A position type may be given its own width — "the pipes are too
        thick" is about electrics, not about the walls, and under RP-2 both are
        heavy. The override changes the WIDTH only; the category stays, so the
        line keeps meaning what it meant and the DXF layer does not move.
        """
        kind = (kind or "electric").strip().lower()
        name = POSITION_STYLES.get(kind, "batten")
        per_type = (self._weights.get("positions") or {})
        w = per_type.get(kind)
        return name, (None if w is None else float(w))

    def line(self, x1, y1, x2, y2, width=0.75, dash=None, color=black, style=None,
             width_override=None):
        """style is an RP-2 line category (see LINE_STYLES) and wins over
        width/dash when given. Prefer it — a named category says WHY the line
        is that weight."""
        if style:
            sw, dash = self.style(style)
            # ⚠ An explicitly passed width WINS over the category's. That is
            # what lets one position type be drawn finer than another while
            # staying in the same RP-2 category — and the default is None, so
            # nothing that does not ask for it is affected.
            width = sw if width_override is None else width_override
        c = self.c; c.saveState(); c.setLineWidth(width); c.setStrokeColor(color)
        if dash: c.setDash(list(dash))   # (array, phase) — pass the pattern as ONE list
        c.line(*self.P(x1, y1), *self.P(x2, y2)); c.restoreState()
        if self.dxf: self.dxf.line(x1, y1, x2, y2)

    def rect(self, x, y, w, h, width=1.0, label=None, fill=None, color=black, style=None):
        if style:
            width, dash = self.style(style)
        c = self.c; c.saveState(); c.setLineWidth(width); c.setStrokeColor(color)
        if style and self.style(style)[1]:
            c.setDash(list(self.style(style)[1]))
        if fill: c.setFillColor(fill)
        px, py = self.P(x, y); self.P(x + w, y + h)   # second call records the far corner
        c.rect(px, py, self.L(w), self.L(h), stroke=1, fill=1 if fill else 0)
        c.restoreState()
        if self.dxf: self.dxf.rect(x, y, w, h)
        if label: self.text(x + w / 2, y + h / 2, label, size=8, center=True, color=grey)

    def circle(self, x, y, r, width=0.75, fill=None, color=black, dash=None, style=None):
        if style:
            width, dash = self.style(style)
        c = self.c; c.saveState(); c.setLineWidth(width); c.setStrokeColor(color)
        if dash: c.setDash(list(dash))   # (array, phase) — pass the pattern as ONE list
        if fill: c.setFillColor(fill)
        self.P(x - r, y - r); self.P(x + r, y + r)
        c.circle(*self.P(x, y), self.L(r), stroke=1, fill=1 if fill else 0); c.restoreState()
        if self.dxf: self.dxf.circle(x, y, r)

    def ellipse(self, cx, cy, a, b, angle_deg=0.0, width=0.75, color=black,
                dash=None, style=None, steps=64):
        """A rotated ellipse, drawn as a polyline so the DXF export gets real
        geometry rather than a curve nobody downstream can read."""
        import math as _m
        if style:
            width, dash = self.style(style)
        t = _m.radians(angle_deg)
        ct, st = _m.cos(t), _m.sin(t)
        pts = []
        for i in range(steps + 1):
            u = 2 * _m.pi * i / steps
            px, py = a * _m.cos(u), b * _m.sin(u)
            pts.append((cx + px * ct - py * st, cy + px * st + py * ct))
        for i in range(steps):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            self.line(x1, y1, x2, y2, width=width, dash=dash, color=color)

    def break_mark(self, x, y, across=0.45, along=0.55, vertical=True):
        """The conventional BREAK: this object continues, but not all of it is drawn.

        ⭐ RP-2 §6.12's Option 1 plate puts one on the boom pipe, and it is what
        licenses the layout's "may not be to scale" note. A boom eighteen feet
        tall with four units on it does not need eighteen feet of paper — it
        needs the four units and their real heights. The break is the honest way
        to say the middle was left out, instead of silently drawing a short boom.

        ⚠ The LABELLED HEIGHTS remain true. The break says the paper is
        compressed; it never says a number is approximate.
        """
        a, b = across / 2, along / 2
        if vertical:
            pts = [(x, y + b), (x + a, y + b * 0.3), (x - a, y - b * 0.3), (x, y - b)]
        else:
            pts = [(x + b, y), (x + b * 0.3, y + a), (x - b * 0.3, y - a), (x - b, y)]
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], width=0.9)

    def fill_poly(self, points, color=white):
        """Paint a closed polygon with no outline — used to OCCLUDE what is under it.

        ⭐ An instrument is drawn as if it sits ABOVE the pipe, even though it
        hangs below: the batten must not run through the symbol (Jerry,
        2026.09.23). That is what makes the body a place you can write a unit
        number. Nothing is stroked here — the outline is drawn afterwards by the
        symbol's own lines, so the DXF export still gets real geometry rather
        than a filled blob.
        """
        if len(points) < 3:
            return
        c = self.c
        c.saveState()
        c.setFillColor(color)
        path = c.beginPath()
        first = True
        for x, y in points:
            px, py = self.P(x, y)
            if first:
                path.moveTo(px, py); first = False
            else:
                path.lineTo(px, py)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
        c.restoreState()

    def text(self, x, y, s, size=8, center=False, color=black, rotate=0, bold=False,
             align=None):
        """`align` is "left" (default), "center" or "right".

        ⚠ Right alignment is not a nicety. A label placed just left of a line and
        drawn LEFT-aligned runs straight across it — which is what the boom
        height labels did: the text started 4" clear of the pipe and then grew
        rightwards over it. Anchoring the END of the string is the only way to
        keep a label clear of something to its right.
        """
        how = align or ("center" if center else "left")
        c = self.c; c.saveState(); c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        px, py = self.P(x, y); c.translate(px, py); c.rotate(rotate)
        dy = -size / 3 if how == "center" else 0
        draw = {"center": c.drawCentredString, "right": c.drawRightString}.get(how, c.drawString)
        draw(0, dy, s)
        c.restoreState()
        if self.dxf: self.dxf.text(x, y, s, size / self.pt_per_ft, rotate=rotate,
                                   center=(how == "center"))

    # ---- theatre objects ----------------------------------------------
    def pipe(self, x1, y, x2, label=None, width=2.0):
        """A hanging position. §6.18: a batten is HEAVY."""
        self.layer("POSITIONS")
        self.line(x1, y, x2, y, style="batten")
        if label: self.text(x1, y + ft(0, 6), label, size=7, bold=True)

    def position(self, pos, label=None, label_at=None):
        """Draw one horizontal hanging position from a plot record.

        `type` decides the drawing, and the distinction is not decoration:

          electric / pipe / grid   one heavy batten line — a pipe is a pipe
          catwalk                  a WALKWAY: two architectural edges you can
                                   stand between, plus the batten you hang from
          truss                    two chords with diagonals

        **A catwalk is not a pipe.** It has a real width, a person stands on it,
        and the instruments hang off its downstage rail rather than its middle —
        so a unit drawn on the centre of a catwalk is drawn three feet from where
        it actually is. At 1/2" scale that is an eighth of an inch on paper and a
        missed shutter cut in the room.

        **⭐ A catwalk is also a FRONT OF HOUSE position** (Jerry, 2026.09.23), so
        it sits OVER THE AUDIENCE — downstage of the plaster line, outside the
        stage rectangle, at negative y in this model. Two things follow and both
        bite:

          * **The sheet has to reach the house.** A plot whose room is the stage
            will clip a catwalk straight off, and the clipping guard is the only
            thing that would say so. `foh_extent()` returns how far downstage the
            positions actually go, so the drawing can be sized to include them.
          * **The throw is long and the angle is steep.** Nothing here needs to
            change for that — the photometrics already work from real geometry —
            but a catwalk unit reading a much lower footcandle than an onstage
            one is correct, not a bug.

        Vertical positions — booms, box booms, ladders — are NOT handled here.
        They are a different drawing problem (RP-2 §6.12) and are deliberately
        out of scope until asked for.
        """
        self.layer("POSITIONS")
        x1, y1 = pos["x1"], pos["y1"]
        foh = pos.get("foh")
        if foh is None:
            foh = (pos.get("type") or "").strip().lower() == "catwalk"
        x2, y2 = pos.get("x2", x1), pos.get("y2", y1)
        kind = (pos.get("type") or "electric").strip().lower()
        label = label if label is not None else pos.get("name", "")

        if kind in ("catwalk", "truss"):
            half = (pos.get("width") or (3.0 if kind == "catwalk" else 1.5)) / 2.0
            # Horizontal only for now, so the offset is in y.
            _edge, _w = self.position_line(kind)
            for side in (1, -1):
                self.line(x1, y1 + side * half, x2, y2 + side * half,
                          style=_edge, width_override=_w)
            if kind == "truss":
                import math
                n = max(2, int(abs(x2 - x1) / max(half * 2, 0.5)))
                for i in range(n):
                    a = x1 + (x2 - x1) * i / n
                    b = x1 + (x2 - x1) * (i + 1) / n
                    self.line(a, y1 - half, b, y1 + half, style="leader")
            else:
                # The pipe units actually hang from. Drawn INBOARD of the
                # downstage edge rather than on it: put it on the edge and the
                # two lines coincide, which reads as one thick rail and loses
                # the fact that there is a pipe at all.
                #
                # ⚠ The real offset varies by house — some hang off the rail
                # itself, some off a pipe a foot inboard. `railOffset` overrides
                # it; take the number off the venue's own section, not from here.
                off = pos.get("railOffset")
                if off is None:
                    off = half * 0.55
                self.line(x1, y1 - off, x2, y2 - off, style="batten",
                          width_override=self.position_line(kind)[1])
            top = max(y1, y2) + half
        else:
            _pstyle, _pw = self.position_line(kind)
            self.line(x1, y1, x2, y2, style=_pstyle, width_override=_pw)
            top = max(y1, y2)

        if label:
            # CAPS on a plot — Jerry, 2026.09.22: "probably caps are more legible."
            text = label.upper() + ("  (FOH)" if foh and "FOH" not in label.upper() else "")
            # ⭐ `label_at` comes from labels.place(), which fits every name around
            # the units and around the other names. Without it the name always
            # went to the pipe's stage-left end, which is how CAT 1 and HOUSE
            # LEFT BOX BOOM 1 ended up on top of each other and on the box boom.
            if label_at:
                self.text(label_at["x"], label_at["y"], text, size=7, bold=True,
                          align=label_at["align"])
            else:
                self.text(x1, top + ft(0, 6), text, size=7, bold=True)

    @staticmethod
    def foh_extent(positions):
        """DEPRECATED — always 0. Kept so callers do not break.

        It existed to extend the sheet downstage for front-of-house positions
        drawn at negative y. That was a wrong model: the room is the whole room,
        house and stage, and an FOH position belongs INSIDE it (Jerry,
        2026.09.24). Nothing needs extra paper any more.
        """
        return 0.0

    def boom(self, pos, units=(), label=None, center_x=None, label_at=None):
        """A vertical position in PLAN: the mount, and the units hatched over it.

        ⭐ In plan a boom is a POINT. Every unit on it shares one x and y and
        differs only in height, so the drawing cannot separate them — which is
        why §6.12 says "hatch or shade acceptable for top view of boom" and puts
        the readable layout BESIDE the plot. Call `boom_elevation()` for that.
        """
        from . import symbols as _sym
        self.layer("POSITIONS")
        x, y = pos["x1"], pos["y1"]
        _sym.draw(self, _sym.boom_mount(pos.get("mount")), x, y, width=1.0)
        if units:
            # One symbol, hatched, standing for the stack. Drawing four on top of
            # each other would just be a heavier blob.
            prims = _sym.for_type(units[0].get("type", ""))
            _sym.draw(self, prims, x, y, rotate_deg=pos.get("rotation", 0.0))
            _sym.draw(self, _sym.hatch(prims), x, y,
                      rotate_deg=pos.get("rotation", 0.0), width=0.35)
        # Jerry, 2026.09.23: "the labels don't need to be on the overhead view of
        # the boom, just on the other view." RP-2's own §6.12 plate agrees — the
        # plan symbols carry no numbers; the layout beside the plot carries them
        # all. So no unit count, no notation, just enough to say WHICH boom this
        # point is, placed OUTBOARD so it never lands on the room or on a
        # position label.
        text = (label if label is not None else pos.get("name", "")).upper()
        if label_at:
            self.text(label_at["x"], label_at["y"], text, size=6, bold=True,
                      align=label_at["align"])
        else:
            out = -1 if center_x is None else (1 if x >= center_x else -1)
            self.text(x + out * ft(1, 4), y - ft(0, 3), text, size=6,
                      bold=True, center=False if out > 0 else True)

    def _unused_marker(self):
        pass

    def boom_elevation(self, pos, units, x, y, height=None, unit_gap=1.5,
                       layout="option1", max_gap=2.5):
        """§6.12 Option 1 — the boom as an elevation beside the plot.

        ⭐ COMPRESSED, with a BREAK MARK where paper was taken out. RP-2's own
        plate does this: unit 1 at 8'-0" sits close above unit 2 at 4'-0" with a
        break between them. A boom eighteen feet tall with four units near the
        bottom does not need eighteen feet of paper; it needs the four units and
        their real heights.

        ⚠ **The labelled heights stay true.** The break says the PAPER is
        compressed. It never says a number is approximate — the heights are the
        whole point of the drawing, and a section that fudged them would be worse
        than none. Every empty run longer than `max_gap` is drawn at `max_gap`
        and marked.

        §6.12 also says "choose only one type of layout per plot"; `layout` is
        carried so a plot can state which, and `check_booms()` enforces the one.
        """
        from . import symbols as _sym
        from . import photometrics as _ph
        self.layer("NOTES")

        # ⭐ WHERE things go is booms.elevation(); this method only puts ink on
        # paper. The /booms endpoint feeds the browser from the same call, so
        # the two drawings cannot disagree about a trim or a break.
        from . import booms as _b
        lay = _b.elevation(pos, units, max_gap)
        breaks, top = lay["breaks"], lay["top"]
        by_unit = {u.get("unit"): u for u in units}
        drawn = [(by_unit.get(u["unit"], u), u["dy"]) for u in lay["units"]]
        no_height = [by_unit.get(u["unit"], u) for u in lay["no_height"]]

        # The pipe, in segments so each break is a real gap rather than a mark
        # sitting on top of an unbroken line.
        cuts = sorted(breaks)
        seg_from = 0.0
        _bstyle, _bw = self.position_line(pos.get("type") or "boom")
        for b in cuts:
            self.line(x, y + seg_from, x, y + b - 0.18, style=_bstyle,
                      width_override=_bw)
            seg_from = b + 0.18
        self.line(x, y + seg_from, x, y + top, style=_bstyle, width_override=_bw)
        for b in cuts:
            self.break_mark(x, y + b)

        self.text(x, y + top + ft(0, 6), (pos.get("name") or "").upper(),
                  size=7, bold=True, center=True)
        self.text(x, y - ft(0, 9), "NOT TO SCALE — heights are the data",
                  size=5, center=True)
        if cuts:
            self.text(x, y - ft(1, 4), f"{len(cuts)} break{'s' if len(cuts) > 1 else ''} "
                      f"— pipe compressed", size=5, center=True)

        for u, dy in drawn:
            uy = y + dy
            self.line(x, uy, x + unit_gap * 0.55, uy, style="leader")
            _sym.draw(self, _sym.for_type(u.get("type", "")), x + unit_gap, uy,
                      rotate_deg=90)
            # Ends 5" clear of the pipe, growing leftwards away from it.
            self.text(x - ft(0, 5), uy - ft(0, 2), self.fmt_len(u["height"]),
                      size=6, align="right")
            self.text(x + unit_gap, uy - ft(0, 3), str(u.get("unit")),
                      size=6, center=True, bold=True)
        for i, u in enumerate(no_height):
            self.text(x + unit_gap, y + top - (i + 1) * 0.5,
                      f"{u.get('unit')}: NO HEIGHT RECORDED", size=5)
        return top

    def unit(self, x, y, num, ch=None, kind="", color_gel=None, focus_to=None, r=None, color_tier=0,
             trim=None, focus_h=5.5, lamp=None, mode=None, lens_rotation=None,
             accessories=None, circuit=None, dimmer=None, address=None, wattage=None,
             control="dimmer-per-circuit", symbol_angle="orthogonal",
             pool_plane=None, show_pool=True, show_focus=True, show_labels=True,
             annotate=False, in_plan=True):
        """A lighting instrument: circle body, unit number inside, channel below,
        gel/type beside, optional focus arrow to a real-world point.

        With trim (hang height, ft) and focus_to, the photometrics are worked out:
        throw, elevation, pan, field/beam pool at focus_h (head height, default 5'-6")
        and center-beam footcandles if the fixture is in photometrics.FIXTURES.
        lamp is a tungsten lamp ("HPL 575"); mode is an LED output mode
        ("Regulated 3200K"). Passing neither uses the fixture's reference figure.

        accessories is a list of names — "top hat", "4-way barn door", "gobo",
        "iris". RP-2 puts gate accessories INSIDE the body and front-of-lens ones
        at the nose, so only the name is given here and the placement is worked
        out. They change nothing photometric: a top hat controls spill, not
        output, and no figure here pretends otherwise. An unrecognised accessory
        is collected in self.warnings — never dropped, because an accessory
        nobody ordered is an accessory nobody brings.

        show_pool draws the field pool at the focus point; annotate prints the
        numbers beside it. Returns the dict (or None if no trim/focus given).
        Everything is recorded in self.units for the schedule and the section.

        ⭐ show_pool, show_focus and show_labels are what the editor's own
        checkboxes mean, carried onto paper. They hide DRAWING only: the
        photometrics are still worked out, the row is still returned and every
        warning is still raised, so turning the pools off cannot turn off the
        check that says a pool never lands. A drawing that hid its own warnings
        would be worse than a cluttered one.

        ⭐ in_plan=False draws NO SYMBOL and NO NOTATION — for a unit on a boom,
        which RP-2 §6.12 draws in an elevation beside the plot instead. In plan a
        boom is a POINT: its units share one x and one y, so drawing them there
        stacks every symbol and every channel circle on the same spot. That is
        what plot_to_pdf did until 2026.09.24, on top of the hatched stack
        Sheet.boom() had already drawn to stand for them.

        ⚠ The FOCUS LEADER and the POOL are still drawn, and the row is still
        computed and recorded. Where a boom's light lands is the most useful
        thing it contributes to a plan — it is only the symbols that cannot be
        told apart at a point."""
        self.layer("UNITS")
        # The symbol itself, drawn to USITT RP-2 (2006). See symbols.py and
        # docs/SYMBOLS.md — the shape and the mark inside it carry the fixture
        # type and the beam angle, which is what an electrician reads first.
        from . import symbols as _sym
        pan = 0.0
        if focus_to and trim is not None:
            from . import photometrics as _ph
            pan = _ph.aim((x, y, trim), (focus_to[0], focus_to[1], focus_h))["pan"]
        # ⭐ RP-2 p.2, in its own words: "It is acceptable to visually orient the
        # angle of each drawn luminaire to either focus points or 90° axes."
        # Jerry, 2026.09.23: "most plots display the instruments on even 90
        # degree mounts... usually it's an option." So `orthogonal` is the
        # default and the true angle is snapped to the nearest quarter turn.
        #
        # 🔴 THE SNAP IS COSMETIC AND MUST STAY THAT WAY. `pan` below is the real
        # aim, and every throw, pool and footcandle is computed from it. A unit
        # drawn at 0° while pointing at 320° is a drawing convention; a unit
        # COMPUTED at 0° would be a lie about the light.
        draw_deg = pan
        if (symbol_angle or "orthogonal").startswith("orth"):
            draw_deg = round(pan / 90.0) * 90.0

        # ⚠ THE LAMP IS PASSED. A retrofit draws §6.16 dots at the lamp
        # housing, and leaving it out here is how the paper would have gone
        # on drawing a tungsten unit while the screen drew an LED.
        _base = _sym.for_type(kind, lens_rotation, lamp)
        # The centre comes from the BARE instrument. Accessories hang off the
        # nose, so measuring the accessorised symbol would drag the "centre"
        # forward out of the body and put the number on a barn door.
        _lo, _hi = _sym._extent(_base)
        _center = (_lo + _hi) / 2.0
        _prims = _base

        # §6.15 / §6.0: a SHADED REAR. RP-2 blackens the back of the symbol for
        # arc sources; Jerry uses the same mark for a 750W Source Four, which is
        # the only place he has seen a wattage called out on a plot at all.
        # Inserted FIRST so the body's own outline is stroked back over it.
        #
        # ⚠ A BLACKENED REAR WOULD SWALLOW THE §6.16 SOURCE DOTS, which sit in
        # the same place. Today the two cannot both happen — shading needs a
        # lamp above 575W and every retrofit burner is 150W — so this is a note
        # for whoever adds a high-wattage LED source, not a live bug.
        if _shade_rear_for(kind, lamp):
            _prims = _sym.shade_rear(_base) + list(_base)

        if accessories:
            _prims, _unknown = _sym.with_accessories(_prims, accessories)
            for w in _unknown:
                self.warnings.append(f"unit {num}: {w}")
        # ⭐ The focus leader goes UNDER the symbol, for the same reason the pipe
        # does: the instrument is drawn as if it sits above everything it is
        # attached to. Drawn after, the leader runs across the body and through
        # the unit number — which is exactly the mess that putting the number
        # inside the body was meant to avoid.
        if focus_to and show_focus:
            self.layer("NOTES")
            self.line(x, y, focus_to[0], focus_to[1], color=grey, style="leader")
            self.circle(focus_to[0], focus_to[1], ft(0, 3), color=grey, style="leader")
            self.layer("UNITS")

        if in_plan:
            _sym.draw(self, _prims, x, y, rotate_deg=draw_deg)

        # §6.14 notation. RP-2 allows leaving categories out rather than
        # cluttering the plot, so only what was supplied is drawn.
        # §6.14.1: hexagon = circuit, rectangle = dimmer, circle = channel. The
        # SHAPE carries the meaning, so a circuit must never be drawn in a circle.
        # Clear the symbol by its own size rather than by a constant. A fixed
        # 11" put the channel circle on top of every ellipsoidal, because an ERS
        # reaches nearly a foot past its yoke — and further still once an
        # accessory is hung on the nose.
        _clear = _sym.radius(_prims) + ft(0, 3)
        if in_plan and show_labels:
            # 🔴 A unit whose colour label would touch its neighbour's is pushed
            # one step FURTHER OUT along the same axis (issue #21). Not up or
            # down: RP-2 §6.14.2 puts colour in front of the unit across the
            # lens, and moving it above or below would put it where the standard
            # says something else lives. A drafter solving this by hand moves it
            # further out, not somewhere else.
            _step = (7.0 / self.pt_per_ft if self.pt_per_ft else 0.39) * 1.5
            _above = _clear + (color_tier or 0) * _step
            from . import dmx as _dmx
            _sym.notation(self, x, y, unit=num, channel=ch, color=color_gel,
                          circuit=circuit, dimmer=dimmer,
                          address=_dmx.plot_number(address, dimmer) if address else None,
                          wattage=wattage,
                          control=control, rotate_deg=draw_deg,
                          body_center=_center, above=_above)
        result = None
        if focus_to:
            fx, fy = focus_to
            if trim is not None:
                from . import photometrics as ph
                a = ph.aim((x, y, trim), (fx, fy, focus_h))
                result = dict(num=num, ch=ch, kind=kind, x=x, y=y, trim=trim, focus=(fx, fy),
                              focus_h=focus_h, accessories=list(accessories or []),
                              circuit=circuit, dimmer=dimmer, **a)
                if kind in ph.FIXTURES:
                    pl = ph.pool(kind, a["throw"], a["elevation"]); result.update(pl)
                    # color_gel may be compound ("R52+R119", "R52/R119"), so ask
                    # gel_factor rather than looking for a single key in GELS.
                    gel_arg, gel_warn = color_gel or None, None
                    if gel_arg:
                        factor, gnote = ph.gel_factor(gel_arg)
                        if factor is None:          # a gel we have no figure for
                            gel_arg, gel_warn = None, gnote
                    fc, note = ph.footcandles(kind, a["throw"], lamp, mode, gel_arg)
                    if gel_warn:
                        note += f" — {gel_warn}; level is for open white"
                    result["fc"], result["fc_note"] = fc, note
                    # ⭐ The REAL shape, not a circle. A cone only cuts a
                    # circle when it points straight down; at 30° elevation a
                    # 26° field lands more than twice as long as it is wide,
                    # and the long end is the one that reaches the scenery.
                    #
                    # ⚠ WORKED OUT WHETHER OR NOT IT IS DRAWN. The note this
                    # raises — the pool grazes the plane and its far edge never
                    # lands — is a fact about the RIG, not about the picture.
                    # Until 2026.09.25 the shape was computed inside the drawing
                    # branch, so unticking `pools` took the warning away with the
                    # ellipse and the plot came out clean by showing less. A
                    # switch that hides a drawing must never hide a finding.
                    sh = ph.pool_shape(kind, (x, y, trim), (fx, fy),
                                       plane_h=pool_plane if pool_plane is not None else focus_h,
                                       focus_h=focus_h)
                    if sh.get("a"):
                        result["pool_shape"] = sh
                    elif sh.get("note"):
                        self.warnings.append(f"unit {num}: {sh['note']}")
                    if show_pool and sh.get("a"):
                        self.layer("NOTES")
                        self.ellipse(sh["cx"], sh["cy"], sh["a"], sh["b"],
                                     sh["angle"], color=grey, style="pool")
                        self.layer("UNITS")
                if annotate:
                    t = f"{self.fmt_len(a['throw'])} @ {a['elevation']:.0f}°"
                    if result.get("field"): t += f" · {self.fmt_len(result['field'])} pool"
                    if result.get("fc"): t += f" · {self.fmt_lux(result['fc'])}"
                    self.text(fx + ft(0, 6), fy - ft(1), t, size=5, color=grey)
        if not hasattr(self, "units"): self.units = []
        self.units.append(result or dict(num=num, ch=ch, kind=kind, x=x, y=y, trim=trim,
                                         focus=focus_to, accessories=list(accessories or [])))
        return result

    def dim(self, x1, y1, x2, y2, text=None, offset_ft=0.0):
        """Dimension line with ticks and a distance label, in the sheet's system.

        ⚠ A room dimension is the most-read number on a plot. It formatted
        feet-and-inches unconditionally, so a metric sheet announced its room
        as 33'-0" beside pools measured in metres."""
        import math
        self.layer("DIMS")
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if text is None:
            text = self.fmt_len(length)
        self.line(x1, y1, x2, y2, style="dimension")
        nx, ny = (-dy / length, dx / length) if length else (0, 1)
        t = ft(0, 4)
        for (x, y) in ((x1, y1), (x2, y2)):
            self.line(x - nx * t, y - ny * t, x + nx * t, y + ny * t, style="dimension")
        ang = math.degrees(math.atan2(dy, dx))
        self.text(x1 + dx / 2 + nx * ft(0, 6), y1 + dy / 2 + ny * ft(0, 6), text,
                  size=7, center=True, rotate=ang)

    def wrap(self, s, width_ft, size=7, bold=False):
        """Break `s` into lines no wider than width_ft, measured in the font it
        will actually be drawn in. A word longer than the line goes on one of
        its own and overruns — shortening it would be inventing a word."""
        font = "Helvetica-Bold" if bold else "Helvetica"
        limit = width_ft * self.pt_per_ft
        lines, cur = [], ""
        for word in s.split():
            trial = f"{cur} {word}".strip()
            if cur and self.c.stringWidth(trial, font, size) > limit:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines or [""]

    def note(self, x, y, s, size=7, width_ft=None):
        """A note in the drawing, in brown.

        ⭐ width_ft WRAPS it. Without a width the string is drawn as one line
        and runs as far as it likes.

        ⚠ The caller used to cut the string to a fixed character count instead.
        On the test plot that ended the room note mid-word, and
        the words it dropped were the ones naming where the dimension came from
        and saying it may not be quoted. A note cut mid-word does not look
        truncated; it looks like the sentence ended, so nobody goes looking for
        the rest. Wrapping keeps all of it and measuring keeps it on the paper.
        """
        self.layer("NOTES")
        if width_ft is None:
            self.text(x, y, s, size=size, color=BROWN)
            return 1
        lines = self.wrap(s, width_ft, size=size)
        line_ft = size * 1.25 / self.pt_per_ft
        for i, line in enumerate(lines):
            self.text(x, y - i * line_ft, line, size=size, color=BROWN)
        # ⚠ P() records only the point it is given, so a block of text counted
        # as its top-left corner alone — which is how a note could run off the
        # sheet with the clipping guard silent. Claim the real footprint.
        widest = max(self.c.stringWidth(ln, "Helvetica", size) for ln in lines)
        self.P(x + widest / self.pt_per_ft, y - (len(lines) - 1) * line_ft)
        return len(lines)

    def _tick(self, v):
        """A ruler tick. Imperial gets feet-and-inches; metric gets plain metres
        — a metric rule is not divided into twelfths, and printing it as though
        it were would be imperial wearing a metric label."""
        from . import units as _units
        if self.unit_system == _units.METRIC:
            return f"{v * _units.M_PER_FOOT:.1f}"
        return _feet_label(v)

    def rulers(self, x0, x1, y0, y1, step=None, bottom=True, side="left",
               size=5.5):
        """Dimension scales along the edges of the plan: X across the bottom,
        Y up one side.

        ⭐ WHAT THIS IS FOR. A scale bar says how long a foot is; it does not
        say where anything IS. With a ruler on two edges you read a position
        straight off the sheet — eleven feet stage right, nineteen upstage —
        without walking a scale rule across the paper and losing your place.

        X runs across the stage and is drawn along the BOTTOM. Y runs upstage
        and is drawn up the SIDE. Said explicitly because the two are easy to
        swap, and a ruler labelled with the wrong axis is worse than none: it
        is confidently wrong and nothing on the sheet contradicts it.

        ⚠ Ticks are labelled in REAL FEET from the plot's own origin, which in
        a black box is the centre of the room — so the numbers go negative
        stage left, and that is correct rather than a bug to hide. A ruler
        renumbered from a corner would disagree with every coordinate in the
        plot file.

        `step` defaults to whatever keeps the labels from colliding at this
        scale: the tick interval is chosen from the SCALE, not from the room,
        so a big room does not silently get a ruler nobody can read.
        """
        if step is None:
            # Roughly half an inch of paper between labels, rounded to a
            # surveyor-friendly interval rather than to whatever the division
            # happened to produce.
            from . import units as _units
            want = 0.5 * inch / self.pt_per_ft
            if self.unit_system == _units.METRIC:
                # ⚠ Choose the interval in METRES and convert back, or a metric
                # ruler ends up ticked every 0.6 m because 2 feet was a round
                # number in the other system.
                want_m = want * _units.M_PER_FOOT
                m = next((c for c in (0.5, 1, 2, 5, 10, 20, 50) if c >= want_m), 50)
                step = m * _units.FOOT_PER_M
            else:
                step = next((c for c in (1, 2, 5, 10, 20, 25, 50, 100) if c >= want), 100)
        self.layer("DIMS")
        pad = 1.2                       # feet of clear air between plan and rule
        tick = 0.45

        def _marks(lo, hi):
            """Tick positions on a whole multiple of step, spanning lo..hi."""
            import math
            first = math.ceil(lo / step) * step
            out, v = [], first
            while v <= hi + 1e-9:
                out.append(round(v, 6))
                v += step
            return out

        if bottom:
            base = y0 - pad
            self.line(x0, base, x1, base, style="dimension")
            for v in _marks(x0, x1):
                self.line(v, base, v, base - tick, style="dimension")
                self.text(v, base - tick - 0.55, self._tick(v), size=size,
                          center=True, color=grey)
            self.text((x0 + x1) / 2.0, base - tick - 1.5, "X — ACROSS",
                      size=size, center=True, color=grey)

        if side:
            at = (x0 - pad) if side == "left" else (x1 + pad)
            out = -1 if side == "left" else 1
            self.line(at, y0, at, y1, style="dimension")
            for v in _marks(y0, y1):
                self.line(at, v, at + out * tick, v, style="dimension")
                self.text(at + out * (tick + 0.25), v, self._tick(v), size=size,
                          align="right" if side == "left" else "left", color=grey)
            # ⚠ BOTH rulers get named. The bottom one alone was what made the
            # axes ambiguous in the first place — a reader who has to work out
            # which scale is which will sooner or later work it out wrongly,
            # and nothing else on the sheet would contradict them.
            self.text(at + out * (tick + 1.9), (y0 + y1) / 2.0, "Y — UPSTAGE",
                      size=size, center=True, color=grey, rotate=90)

    # ---- §6.18 reference lines

    def center_line(self, x, y0, y1):
        """§6.18: the center line is MEDIUM, chain-dashed."""
        self.layer("BASE")
        self.line(x, y0, x, y1, style="centerline", color=grey)

    def plaster_line(self, y, x0, x1):
        """§6.18: the plaster line is MEDIUM, evenly dashed."""
        self.layer("BASE")
        self.line(x0, y, x1, y, style="plasterline", color=grey)

    # ---- sheet furniture ----------------------------------------------
    def finish(self):
        """Scale bar, one-inch check, title block, then save."""
        c = self.c; W, H = self.page_pt; m = self.margin
        # clipping check — a drawing that runs off the sheet is worse than no drawing
        x0b, y0b, x1b, y1b = self._bounds
        if x1b > -1e8 and (x0b < m or y0b < m or x1b > W - m or y1b > H - m - 1.3 * inch):
            real_w = (x1b - x0b) / self.pt_per_ft; real_h = (y1b - y0b) / self.pt_per_ft
            avail_w = (W - 2 * m) / inch; avail_h = (H - 2 * m - 1.3 * inch) / inch
            fit = min(avail_w / real_w, avail_h / real_h) if real_w and real_h else 0
            best = max((k for k, v in SCALES.items() if v <= fit), key=lambda k: SCALES[k], default=None)
            # ⚠ Say WHICH EDGE and by how much. This used to report only the
            # spans against the sheet size, so a drawing that FITS but is placed
            # off one edge read as "too big" — sending the reader to change the
            # scale when the fault was a stray coordinate. The section reported
            # 53' against a 70' sheet and was clipped all the same: one sight
            # point at y = -14 lay ten feet off the left edge.
            over = []
            if x0b < m: over.append(f"{(m - x0b) / self.pt_per_ft:.1f}' off the LEFT")
            if y0b < m: over.append(f"{(m - y0b) / self.pt_per_ft:.1f}' off the BOTTOM")
            if x1b > W - m: over.append(f"{(x1b - (W - m)) / self.pt_per_ft:.1f}' off the RIGHT")
            if y1b > H - m - 1.3 * inch:
                over.append(f"{(y1b - (H - m - 1.3 * inch)) / self.pt_per_ft:.1f}' off the TOP")
            edges = ("; ".join(over) + ". ") if over else ""
            # ⭐ And name a sheet that WOULD work. "Use a bigger sheet" leaves the
            # reader to test paper sizes by hand; the table is right here, so
            # the smallest one that fits at this scale is a lookup.
            need_w = real_w * self.paper_in_per_ft + 2 * (m / inch)
            need_h = real_h * self.paper_in_per_ft + 2 * (m / inch) + 1.3
            def _fits(_w, _h):
                return _w >= need_w and _h >= need_h

            # ⚠ TURN THE PAPER FIRST. Jerry, 2026.09.24: "we can suggest portrait
            # if needed." Sending someone to a larger sheet when the one already
            # in the plotter would hold the drawing the other way round is advice
            # that costs paper for nothing.
            bigger = None
            _pw, _ph = sorted(self.page_in)
            _other = (_pw, _ph, "portrait") if self.landscape else (_ph, _pw, "landscape")
            if _fits(_other[0], _other[1]):
                bigger = f'{self.page_name} {_other[2]} ({_other[0]:g}" x {_other[1]:g}")'
            else:
                for _name, (_aw, _ah) in sorted(PAGES.items(), key=lambda kv: kv[1][0] * kv[1][1]):
                    for _w, _h, _o in ((_aw, _ah, "portrait"), (_ah, _aw, "landscape")):
                        if _fits(_w, _h):
                            bigger = f'{_name} {_o} ({_w:g}" x {_h:g}")'
                            break
                    if bigger:
                        break
            here = (f'{self.page_name} {"landscape" if self.landscape else "portrait"} '
                    f'({self.page_in[0]:g}" x {self.page_in[1]:g}")')
            msg = (f"CLIPPED: {edges}drawing spans {real_w:.1f}' x {real_h:.1f}' but {here} holds "
                   f"{avail_w/self.paper_in_per_ft:.1f}' x {avail_h/self.paper_in_per_ft:.1f}' at {self.scale_label}. "
                   + (f'Largest standard scale that fits this sheet: {best}" = 1\'-0". ' if best else "")
                   + (f"Or keep {self.scale_label} on {bigger}."
                      if bigger else "No standard sheet holds it at this scale."))
            self.warnings.append(msg); print("⚠", msg, file=sys.stderr)
        self.dxf, _dxf = None, self.dxf          # sheet furniture stays off the DXF
        # border
        c.setLineWidth(HEAVY); c.rect(m, m, W - 2 * m, H - 2 * m)      # §6.18 drawing border
        if self.base_note:
            c.setFillColor(grey); c.setFont("Helvetica", 6); c.drawString(m + 6, m + 6, self.base_note)
        # title block, lower right
        tb_w, tb_h = 4.0 * inch, 1.1 * inch
        x0, y0 = W - m - tb_w, m
        c.setLineWidth(HEAVY); c.rect(x0, y0, tb_w, tb_h)             # §6.18 title block border
        c.setFillColor(GREEN); c.setFont("Helvetica-Bold", 11)
        c.drawString(x0 + 6, y0 + tb_h - 15, self.meta["show"] or "Untitled")
        c.setFillColor(black); c.setFont("Helvetica", 8)
        from reportlab.pdfbase.pdfmetrics import stringWidth
        for i, key in enumerate(("venue", "sheet")):
            t = self.meta[key]
            if stringWidth(t, "Helvetica", 8) > tb_w - 12:
                while stringWidth(t + "…", "Helvetica", 8) > tb_w - 12: t = t[:-1]
                t += "…"
            c.drawString(x0 + 6, y0 + tb_h - 27 - 12 * i, t)
        import datetime
        c.drawString(x0 + 6, y0 + tb_h - 51, f"Scale {self.scale_label}   Rev {self.meta['rev']}   "
                                              f"{datetime.date.today().strftime('%Y.%m.%d')}")
        if self.meta["designer"]:
            c.setFillColor(BROWN); c.setFont("Helvetica-Bold", 8)
            c.drawString(x0 + 6, y0 + 6, self.meta["designer"])
        # "Print at 100%" is a fact about the SHEET — the scale bar is only true
        # at actual size — so it is always drawn. The studio name in front of it
        # is not, and appears only if the plot carries one.
        c.setFillColor(grey); c.setFont("Helvetica", 6)
        foot = "print at 100% / Actual size"
        if self.meta["studio"]:
            foot = f"{self.meta['studio']} — {foot}"
        c.drawRightString(x0 + tb_w - 6, y0 + 6, foot)
        # scale bar: 0 to 10 ft in 1-ft ticks, left of title block
        # ⚠ Positioned from the bar's REAL width. It used to be placed as though
        # it were ten feet wide and then drawn ten metres wide, so on a metric
        # sheet it started in the right place and ended a long way past the edge.
        sx, sy = x0 - 0.4 * inch - self.scale_bar_plan()[2], m + 0.35 * inch
        c.setStrokeColor(black); c.setFillColor(black); c.setLineWidth(1)
        # ⚠ The bar is divided in the unit the sheet is DRAWN in — ten feet on an
        # imperial sheet, ten metres on a metric one. A metric drawing with a
        # bar ticked in feet is the one thing on the page somebody would measure
        # against, and it would be lying.
        divs, step, total, per_div = self.scale_bar_plan()
        for i in range(divs):
            c.rect(sx + i * step, sy, step, 5, stroke=1, fill=(i % 2 == 0))
        c.setFont("Helvetica", 6)
        # Ends always; the middle only when it lands on a whole division.
        marks = [0, divs] if divs % 2 else [0, divs // 2, divs]
        unit = "m" if self.is_metric_scale else "'"
        for i in marks:
            v = i * per_div
            txt = f"{v:g}"
            c.drawCentredString(sx + i * step, sy - 8,
                                f"{txt} m" if self.is_metric_scale else f"{txt}'")
        c.drawString(sx, sy + 9, f"Scale {self.scale_label}")
        # A PRINT CHECK, not a drawing scale: it proves the sheet came out of the
        # printer at 100% rather than fitted to the page. 50 mm on a metric sheet
        # because nobody reaches for an inch rule to check a 1:50 drawing.
        cx, cy = sx, sy + 0.32 * inch
        if self.is_metric_scale:
            bar_pt, bar_says = 50.0 / 25.4 * inch, "this bar is 50 mm when printed at 100%"
        else:
            bar_pt, bar_says = 72.0, 'this bar is 1" when printed at 100%'
        c.setLineWidth(1); c.rect(cx, cy, bar_pt, 4, stroke=1, fill=0)
        c.drawString(cx + bar_pt + 4, cy, bar_says)
        c.save()
        if _dxf and self.dxf_path: _dxf.save(self.dxf_path)


def _shade_rear_for(kind, lamp=None):
    """Should this instrument's back be blackened? (§6.15, and Jerry's 750 mark.)

    Two cases, one mark:
      · an ARC source — RP-2 §6.15 blackens the rear of HMI and the like;
      · a tungsten unit carrying MORE than the default lamp — Jerry, 2026.09.23:
        "the only [wattage] I've seen on plots is 750w S4 where the back is
        blackened, like they have for HMI lamps in the spec."

    ⚠ It reads the lamp, not the fixture: the same Source Four is a 575 or a 750
    depending on what is in it, so shading by fixture type would mark the whole
    rig or none of it.
    """
    from . import photometrics as _ph
    key, row, _ = _ph.lookup(kind)
    if row and str(row.get("family", "")).lower() in ("arc", "hmi"):
        return True
    if not lamp:
        return False
    w = _ph.lamp_watts(lamp)
    default = _ph.lamp_watts(_ph.DEFAULT_LAMP)
    return bool(w and default and w > default)


def compress_heights(heights, max_gap=2.5):
    """Where to DRAW a boom's units when the pipe is longer than the paper.

    ⚠ The arithmetic moved to booms.py so the browser can ask for it too — it
    was about to be retyped in TypeScript, which is how the screen and the paper
    drifted three times in one week. This name is kept because the suites and
    plot_to_pdf call it.
    """
    from . import booms as _b
    return _b.compress(heights, max_gap)


def section(path, units, deck_length, grid_height, scale="1/2", page="ARCH_D", landscape=True,
            axis="y", head_h=5.5, **meta):
    """Side elevation from a list of unit dicts (as Sheet.units records them).

    axis="y": the cut runs upstage–downstage; horizontal position is each unit's y.
    axis="x": the cut runs across the stage; horizontal position is each unit's x.
    Draws the deck, the grid/trim, each unit at its trim, the beam's center line to
    the focus point at head height, and the field-edge lines to the deck.
    """
    from . import photometrics as ph
    s = Sheet(path, page=page, scale=scale, landscape=landscape,
              sheet=meta.pop("sheet", "Section"), **meta)
    s.origin(ft(3), ft(3))
    s.layer("BASE")
    s.rect(0, -ft(0, 4), deck_length, ft(0, 4), width=1.2, fill=grey)          # the deck, 4" thick
    s.line(0, grid_height, deck_length, grid_height, width=0.5, dash=(4, 4), color=grey)
    s.text(deck_length + ft(0, 6), grid_height, f"grid {s.fmt_len(grid_height)}", size=6, color=grey)
    s.line(0, head_h, deck_length, head_h, width=0.3, dash=(1, 3), color=grey)
    s.text(deck_length + ft(0, 6), head_h, f"head height {s.fmt_len(head_h)}", size=6, color=grey)
    for u in units:
        if u.get("trim") is None or not u.get("focus"): continue
        h = u["y"] if axis == "y" else u["x"]
        fh = u["focus"][1] if axis == "y" else u["focus"][0]
        s.layer("POSITIONS"); s.circle(h, u["trim"], ft(0, 5), width=1.0, fill=white)
        s.text(h, u["trim"], str(u["num"]), size=6, center=True, bold=True)
        s.text(h, u["trim"] + ft(0, 10), f"trim {s.fmt_len(u['trim'])}", size=5, center=True, color=grey)
        s.layer("NOTES"); s.line(h, u["trim"], fh, head_h, width=0.6, dash=(3, 2))
        s.circle(fh, head_h, ft(0, 3), width=0.5)
        f = ph.FIXTURES.get(u.get("kind"))
        if f and f["field"]:
            e = math.radians(u["elevation"]); half = math.radians(f["field"]) / 2
            direction = 1 if fh >= h else -1
            for ang in (e - half, e + half):
                if ang <= 0.01: continue
                run = u["trim"] / math.tan(ang)                                # to the deck
                end = h + direction * run
                if 0 <= end <= deck_length:
                    s.line(h, u["trim"], end, 0, width=0.4, color=grey)
                else:                                                          # leaves the deck: stop at the edge
                    edge = deck_length if direction > 0 else 0
                    frac = (edge - h) / (end - h) if end != h else 1
                    s.line(h, u["trim"], edge, u["trim"] * (1 - frac), width=0.4, color=grey, dash=(1, 2))
            lab = f"{u['kind']} · {s.fmt_len(u['throw'])} @ {u['elevation']:.0f}°"
            if u.get("fc"): lab += f" · {s.fmt_lux(u['fc'])}"
            s.text(fh, -ft(1, 2), lab, size=5, center=True, color=grey)
    s.finish()
    return s


# ⭐ Standard scales only, biggest first. Jerry, 2026.09.24: "we should be able
# to zoom in as long as all the objects are still on the page."
#
# ⚠ STANDARD ones. An electrician measures off a drawing with a scale rule, so
# one at 0.31" = 1'-0" is a drawing nobody can measure. Filling the sheet by
# solving for a ratio would break the tool it is read with, which is why this
# walks a fixed list.
FIT_SCALES = ["1", "3/4", "1/2", "3/8", "1/4", "1/8"]
# ⭐ Largest first, same as the imperial list. These are the ratios an architect
# actually draws at — 1:30 and 1:40 exist but are not standard here, and a scale
# nobody recognises is worse than a smaller one everybody does.
FIT_SCALES_METRIC = ["1:10", "1:20", "1:25", "1:50", "1:100"]


def fit_scales(system=None):
    """The ladder to try, for the system the plot is written in."""
    from . import units as _u
    return list(FIT_SCALES_METRIC if system == _u.METRIC else FIT_SCALES)


def largest_scale(render_fn, system=None):
    """The biggest standard scale at which nothing runs off the sheet.

    `render_fn(scale, path)` draws the whole thing and returns its Sheet.

    Rendered and CHECKED rather than predicted: the clipping guard already knows
    what "fits" means, and a second implementation of that arithmetic would be
    one more thing to keep in step. Text, the title block and the scale bar are
    sized in POINTS, so they occupy more FEET as the scale gets smaller — a span
    measured once and divided does not survive that. A render is about 0.1s.
    """
    import contextlib
    import io
    import os as _os
    import tempfile
    probe = _os.path.join(tempfile.mkdtemp(), "fit.pdf")
    ladder = fit_scales(system)
    for k in ladder:
        with contextlib.redirect_stderr(io.StringIO()):
            sheet = render_fn(k, probe)
        if not any("CLIPPED" in w for w in sheet.warnings):
            return k
    # ⚠ Never silently. Nothing fits, so take the smallest and let the guard say
    # so on the real render — a drawing quietly made at a scale that clips is
    # exactly the failure the guard exists to catch.
    return ladder[-1]


def check(path):
    """Find the 1-inch check bar and report its width in points (want 72.0)."""
    import fitz
    doc = fitz.open(path)
    for pno, page in enumerate(doc):
        for d in page.get_drawings():
            for item in d["items"]:
                if item[0] == "re":
                    r = item[1]
                    if 3 <= r.height <= 5 and 60 <= r.width <= 84:
                        print(f"page {pno+1}: check bar {r.width:.2f} pt wide "
                              f"({'OK' if abs(r.width-72) < 0.05 else 'OFF'} — want 72.00)")
                        return r.width
    print("no check bar found"); return None


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        check(sys.argv[2])
    else:
        print(__doc__)
