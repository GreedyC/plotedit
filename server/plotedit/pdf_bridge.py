#!/usr/bin/env python3
"""A venue's ground plan out of a PDF, as polylines in feet.

⭐ Jerry, 2026.09.24: "could we do the same for PDFs too?" Venues send PDFs far
more often than they send DXFs — a PDF is what comes back when you ask a house
for its plan, because it is what their drawing office exports for everybody.

⚠ A PDF HAS NO UNITS, only paper. Its coordinates are points, 72 to the printed
inch, so the only way to reach feet is the drawing's SCALE — the "1/4\" = 1'-0\""
printed in its title block. That figure has to come from the reader; nothing in
the file states it in a form anything can read. Get it wrong by a factor of two
and the plan is still a perfectly plausible drawing of a different room, which
is why the importer reports the size it arrived at and says to check it.

⚠ AND NO LAYERS. A DXF import can take WALLS and leave the dimensions and the
title block behind; a PDF is one flat pile of strokes, so the border, the
title block and every dimension line come in with the walls. That is a real
difference in what the two formats can give you, and saying so is better than
importing half of it by a guess about what looks structural.
"""
import fitz

# The standard architectural scales, as inches of paper per foot of building.
SCALES = {"1/16": 0.0625, "3/32": 0.09375, "1/8": 0.125, "3/16": 0.1875,
          "1/4": 0.25, "3/8": 0.375, "1/2": 0.5, "3/4": 0.75, "1": 1.0,
          "1:50": 72 / (50 * 12), "1:100": 72 / (100 * 12)}

PT_PER_INCH = 72.0


def feet_per_point(scale) -> float:
    """How many feet one PDF point is worth, at a given drawing scale.

    `scale` is a key of SCALES ("1/4"), or a number of inches per foot.
    """
    inches_per_foot = SCALES[scale] if isinstance(scale, str) else float(scale)
    if inches_per_foot <= 0:
        raise ValueError("a scale must be greater than zero")
    return 1.0 / (inches_per_foot * PT_PER_INCH)


def pages(path):
    """What is in the file, so the reader can choose before importing.

    `items` is the count of VECTOR drawing items on the page. A scanned plan —
    a photograph of a drawing — has none, and no amount of scale arithmetic will
    get geometry out of it. Reporting the count says which kind of PDF this is
    rather than importing nothing and looking broken.
    """
    out = []
    with fitz.open(path) as doc:
        for n, page in enumerate(doc):
            items = sum(len(g["items"]) for g in page.get_drawings())
            out.append({
                "page": n + 1,
                "width_in": round(page.rect.width / PT_PER_INCH, 2),
                "height_in": round(page.rect.height / PT_PER_INCH, 2),
                "items": items,
                "images": len(page.get_images()),
            })
    return out


def raster(path, page=1, dpi=150):
    """One page as a PNG, for a plan that has no vectors in it.

    ⭐ A PHOTOGRAPH OF A ROOM CANNOT BE TRACED INTO GEOMETRY, and pretending
    otherwise would put invented lines on a light plot. What it CAN be is a
    backdrop: the designer sees the room, draws over it, and the drawing is
    theirs rather than the picture's.

    🔴 IT IS NOT A SOURCE OF DIMENSIONS. Nothing measured off this image may
    reach the paperwork. The room's width and depth are still typed in by the
    person who measured them, and the calibration below only decides how big the
    picture is DRAWN — never how big the room is.

    Returns (png_bytes, width_in, height_in) at the page's own size, so the
    caller knows the aspect ratio before it has scaled anything.
    """
    with fitz.open(path) as doc:
        if page < 1 or page > doc.page_count:
            raise ValueError(f"no page {page} — the file has {doc.page_count}")
        pg = doc[page - 1]
        # ⚠ 150 dpi, not 300. This is a tracing backdrop viewed at screen size
        # and printed behind a plot; doubling the dpi quadruples the bytes for
        # detail nobody is measuring off.
        pix = pg.get_pixmap(dpi=dpi)
        return (pix.tobytes("png"),
                round(pg.rect.width / PT_PER_INCH, 3),
                round(pg.rect.height / PT_PER_INCH, 3))


def _flatten(item, height):
    """One PDF drawing item as a list of point lists, in PDF points, y UP.

    ⚠ fitz measures y DOWNWARDS from the top of the page; a plot measures it
    upwards from the bottom. Without the flip the room arrives upside down —
    which on a symmetrical ground plan looks entirely reasonable until somebody
    hangs the front of house over the back wall.
    """
    def P(p):
        return (p.x, height - p.y)

    kind = item[0]
    if kind == "l":
        return [[P(item[1]), P(item[2])]]
    if kind == "re":
        r = item[1]
        return [[(r.x0, height - r.y0), (r.x1, height - r.y0),
                 (r.x1, height - r.y1), (r.x0, height - r.y1),
                 (r.x0, height - r.y0)]]
    if kind == "qu":
        q = item[1]
        pts = [P(q.ul), P(q.ur), P(q.lr), P(q.ll)]
        return [pts + [pts[0]]]
    if kind == "c":
        # A cubic bezier, flattened. Eight segments is invisible at any scale a
        # ground plan is read at, and a backdrop does not need more.
        p0, p1, p2, p3 = (P(item[i]) for i in range(1, 5))
        pts = []
        for i in range(9):
            t = i / 8
            u = 1 - t
            pts.append((
                u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
            ))
        return [pts]
    return []


def paths(path, page=1, scale="1/4", origin="bounding-box"):
    """A page's vectors as polylines in FEET.

    origin="bounding-box" moves the drawing so its own bottom-left corner is at
    (0, 0). ⚠ This is the default because a PDF's origin is the corner of the
    PAPER, not of the building — leaving it alone puts the plan wherever the
    title block happens to have pushed it, which is tens of feet away at any
    normal scale. Pass origin="page" to keep the paper's own coordinates.
    """
    fpp = feet_per_point(scale)
    with fitz.open(path) as doc:
        if not 1 <= page <= len(doc):
            raise ValueError(f"page {page} — the file has {len(doc)}")
        pg = doc[page - 1]
        h = pg.rect.height
        raw = []
        for group in pg.get_drawings():
            for item in group["items"]:
                raw.extend(_flatten(item, h))

    if not raw:
        return {"paths": [], "extents": None, "scale": scale,
                "note": "no vector geometry on that page — if the plan is a scan, "
                        "there is nothing to import"}

    xs = [p[0] for poly in raw for p in poly]
    ys = [p[1] for poly in raw for p in poly]
    ox, oy = (min(xs), min(ys)) if origin == "bounding-box" else (0.0, 0.0)

    out = [{"layer": "pdf",
            "points": [[round((x - ox) * fpp, 4), round((y - oy) * fpp, 4)] for x, y in poly]}
           for poly in raw]
    ext = [round((min(xs) - ox) * fpp, 3), round((min(ys) - oy) * fpp, 3),
           round((max(xs) - ox) * fpp, 3), round((max(ys) - oy) * fpp, 3)]
    return {"paths": out, "extents": ext, "scale": scale,
            "note": f"{len(out)} paths at {scale}\" = 1'-0\". A PDF has no layers, so "
                    f"the border, the title block and the dimensions came in too."}
