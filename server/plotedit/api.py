#!/usr/bin/env python3
"""The read-only half of the service: what the fixtures are, what the gels are,
and what a given rig would actually do.

    cd server && uvicorn plotedit.api:app --reload
    curl localhost:8000/fixtures

Nothing here writes a file or changes state. Export and editing come later.

⚠ Every photometric and gel figure carries its source, and the API passes those
sources through rather than stripping them. A number without provenance is how
the EDLT figures got mistaken for standard-tube figures in the first place.
"""
import io
import json
import os
import tempfile
import unicodedata
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import photometrics as ph
from . import positions as P
from . import exports, dxf_bridge, pdf_bridge, symbols as sym
from . import booms
from . import store as plotstore
from . import labels as lbl
from . import fixture_names

app = FastAPI(
    title="plotedit",
    description="Light plot computation. Read-only.",
    version="0.1.0",
)

# The front end is served from a dev server on another port during development.
# Localhost only — this is a tool that runs on the designer's laptop at tech,
# not a service on a network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# ----------------------------------------------------------------- models

class Instrument(BaseModel):
    """One unit on the plot. Field names follow the Vectorworks/Lightwright
    exchange, so paperwork.py imports old shows with no translation."""
    unit: Optional[int] = None
    channel: Optional[int] = None
    type: str = Field(..., description='A key in FIXTURES, e.g. "S4 26"')
    x: float = Field(..., description="Feet, stage coordinates")
    y: float = Field(..., description="Feet")
    trim: Optional[float] = Field(None, description="Hang height in feet")
    focus_x: Optional[float] = None
    focus_y: Optional[float] = None
    focus_h: float = Field(5.5, description="Head height at the focus point, feet")
    color: Optional[str] = Field(None, description='"R52+R119" stacks, "R52/R119" splits')
    lamp: Optional[str] = Field(None, description='e.g. "HPL 575" for a tungsten rig')
    mode: Optional[str] = Field(None, description='LED output mode, e.g. "Regulated 3200K"')
    position: Optional[str] = None
    purpose: Optional[str] = None


class ComputeRequest(BaseModel):
    instruments: List[Instrument]
    # The height to cut the pools at — 0 for the deck, ~5'-2" for a face,
    # 5'-6" for the top of a head. Separate from where a unit is AIMED.
    pool_plane: Optional[float] = None
    # ⭐ Which system to FORMAT the answers in. The arithmetic is unchanged —
    # it is all feet either way — so this only decides how a number is written
    # back. Absent means imperial, which is every request sent before today.
    units: Optional[str] = None

class WashRequest(BaseModel):
    type: str
    throw: float
    width: Optional[float] = Field(None, description="Feet of acting area to cover")
    rule: str = Field("field-to-beam",
                      description="field-to-beam | beam-to-beam | field-to-field")
    # Same as ComputeRequest: formatting only, arithmetic unchanged. Without it
    # the wash calculator answers a metric plot in feet.
    units: Optional[str] = None


# ----------------------------------------------------------------- endpoints

@app.get("/health")
def health() -> Dict[str, Any]:
    # ⭐ The version is here rather than in its own endpoint because the editor
    # already calls this on boot. A tester reporting something has to be able to
    # say which build they saw it in.
    from .version import version as _v
    return {"ok": True, "fixtures": len(ph.FIXTURES), "gels": len(ph.GELS),
            "version": _v()}


@app.get("/fixtures")
def fixtures() -> Dict[str, Any]:
    """Every fixture with its beam and field angles, candela, and its SOURCE.

    Keys say which lens tube: "Lustr 26 EDLT" is not the same fixture as a Lustr
    on a standard tube, and ETC publishes no figures for the latter.
    """
    out = {}
    for k, f in ph.FIXTURES.items():
        penumbra = (f["field"] - f["beam"]) if f["field"] and f["beam"] else None
        out[k] = {
            "field": f["field"],
            "beam": f["beam"],
            "penumbra_deg": round(penumbra, 1) if penumbra else None,
            "candela": f["cd"],
            "reference_lamp": f["ref_lamp"],
            "family": f["family"],
            "modes": list(f.get("modes", {})) or None,
            "source": f["source"],
        }
    return {"count": len(out), "fixtures": out}


@app.get("/gels")
def gels() -> Dict[str, Any]:
    """Gel transmissions, each with its source.

    Rosco publishes transmission for color filters on the website but NOT for
    the diffusions — those figures come from the myColor swatch app.
    """
    return {
        "count": len(ph.GELS),
        "notation": {
            "+": "stacked in one frame — transmissions multiply",
            "/": "a split frame, two gels cut diagonally — they do NOT multiply",
        },
        "gels": {k: {"name": v["name"], "transmission": v["t"], "source": v["source"]}
                 for k, v in ph.GELS.items()},
    }


@app.post("/compute")
def compute(req: ComputeRequest) -> Dict[str, Any]:
    """Throw, elevation, pan, pools and footcandles for each instrument.

    An instrument with no trim or no focus point gets `computed: false` and an
    explanation rather than a guessed number.
    """
    from . import units as _u
    sysm = _u.system_of({"units": req.units})
    results = []
    for i, inst in enumerate(req.instruments):
        row: Dict[str, Any] = {"index": i, "unit": inst.unit, "channel": inst.channel,
                               "type": inst.type, "computed": False}
        # ⭐ The LOAD, on every row — before the early returns, because a unit
        # with no trim still draws current. Wattage is a fact about the fixture
        # and its lamp; it does not wait on a focus point, and a load table that
        # skipped un-aimed units would under-report the circuit they are on.
        _w, _wnote = ph.watts_for(inst.type, inst.lamp, inst.mode)
        row["watts"], row["watts_note"] = _w, _wnote
        if inst.type not in ph.FIXTURES:
            row["note"] = f"{inst.type} is not in the fixture table"
            results.append(row); continue
        if inst.trim is None or inst.focus_x is None or inst.focus_y is None:
            row["note"] = "needs a trim height and a focus point"
            results.append(row); continue

        a = ph.aim((inst.x, inst.y, inst.trim),
                   (inst.focus_x, inst.focus_y, inst.focus_h))
        row.update(computed=True,
                   throw=round(a["throw"], 2), throw_ft=ph.fmt_ft(a["throw"], sysm),
                   elevation=round(a["elevation"], 1), pan=round(a["pan"], 1))

        pool = ph.pool(inst.type, a["throw"], a["elevation"])
        if pool.get("field"):
            row["field"] = round(pool["field"], 2)
            row["field_ft"] = ph.fmt_ft(pool["field"], sysm)
        if pool.get("beam"):
            row["beam"] = round(pool["beam"], 2)
            row["beam_ft"] = ph.fmt_ft(pool["beam"], sysm)
        if pool.get("on_deck_length"):
            row["on_deck_ft"] = ph.fmt_ft(pool["on_deck_length"], sysm)

        # ⭐ The REAL pool: an ellipse, not a circle. A cone only cuts a circle
        # when it points straight down. `pool_plane` chooses the height to cut
        # at — the deck, a face, the top of a head — which is a different thing
        # from where the unit is AIMED.
        sh = ph.pool_shape(inst.type, (inst.x, inst.y, inst.trim),
                           (inst.focus_x, inst.focus_y),
                           plane_h=req.pool_plane if req.pool_plane is not None else inst.focus_h,
                           focus_h=inst.focus_h)
        if sh.get("a"):
            row["pool"] = {k: (round(v, 3) if isinstance(v, (int, float)) else v)
                           for k, v in sh.items() if k != "note"}
        elif sh.get("note"):
            # Never silently. A pool that cannot be drawn is a fact about the
            # focus, and the circle that used to be drawn there hid it.
            row["pool_note"] = sh["note"]

        gel_arg = inst.color or None
        if gel_arg:
            factor, gnote = ph.gel_factor(gel_arg)
            row["gel_note"] = gnote
            if factor is None:
                gel_arg = None
                row["gel_warning"] = "no transmission figure; level is for open white"
        fc, note = ph.footcandles(inst.type, a["throw"], inst.lamp, inst.mode, gel_arg)
        row["footcandles"] = round(fc) if fc else None
        row["footcandles_note"] = note
        results.append(row)

    return {"count": len(results), "instruments": results}


@app.post("/wash")
def wash(req: WashRequest) -> Dict[str, Any]:
    """Spacing for a wash, and how many units cover a given width.

    Default rule is field-to-beam: each unit's field edge lands on the next
    unit's beam edge, so the overlap sits between the two beams.
    """
    try:
        w = ph.wash_spacing(req.type, req.throw, req.rule)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    from . import units as _u
    _ws = _u.system_of({"units": req.units})
    out = {"type": req.type, "throw": req.throw, "rule": req.rule,
           "spacing": round(w["spacing"], 2), "spacing_ft": ph.fmt_ft(w["spacing"], _ws),
           "field_radius_ft": ph.fmt_ft(w["field_r"], _ws),
           "beam_radius_ft": ph.fmt_ft(w["beam_r"], _ws),
           "penumbra_ft": ph.fmt_ft(w["penumbra"], _ws)}
    if req.width:
        r = ph.wash_row(req.type, req.throw, req.width, req.rule)
        out["row"] = {"count": r["count"], "spacing_ft": ph.fmt_ft(r["spacing"], _ws),
                      "ideal_ft": ph.fmt_ft(r["ideal"], _ws),
                      "positions": [round(p, 2) for p in r["positions"]]}
    return out


@app.get("/lens")
def lens(pool: float, throw: float, family: str = "S4") -> Dict[str, Any]:
    """Which barrel gives a pool of this size at this throw."""
    rows = ph.lens_for(pool, throw, family)
    if not rows:
        raise HTTPException(status_code=400, detail=f"no fixtures in family {family!r}")
    return {"wanted_ft": pool, "throw": throw, "family": family,
            "options": [{"type": k, "field_ft": ph.fmt_ft(d), "error_ft": round(e, 2)}
                        for k, d, e in rows]}


# ----------------------------------------------------------------- export

class ExportRequest(BaseModel):
    """A whole plot, as the editor holds it. Loosely typed on purpose — the
    format's own types live in web/src/plot.ts and the server should not
    reject a plot for carrying a field it does not know about."""
    plot: Dict[str, Any]
    # ⭐ "fit" zooms in to the largest STANDARD scale at which nothing runs off
    # the sheet. An explicit scale is still honoured — a plot issued at 1/4"
    # stays at 1/4" when it is reissued.
    scale: str = "fit"
    page: str = "ARCH_D"
    landscape: bool = True
    # ⭐ What the editor's own checkboxes mean, carried onto paper. A designer
    # who turns the pools off to read the plot expects the print to match the
    # screen; before these, Export gave back everything regardless and the only
    # way to issue a clean plan was to delete the focus points.
    # Defaulting to True keeps every existing caller — and every saved plot —
    # drawing exactly what it drew before.
    showPools: bool = True
    showFocus: bool = True
    showLabels: bool = True
    # The height the pools are cut at, in feet. None means the editor did not
    # choose one, and each unit falls back to its own focus height.
    poolPlane: Optional[float] = None
    # ⭐ Rulers along the plan's edges: X across the bottom, Y up one side.
    # true for the defaults, or {"side": "right", "step": 5} to place them.
    rulers: Optional[Any] = None


def _attach(body: bytes, media: str, filename: str) -> Response:
    """Send a file as a download.

    ⚠ HTTP headers are latin-1. An em dash in a show title — and Jerry's titles
    have them — raises UnicodeEncodeError on the way out. RFC 5987 is the fix:
    an ASCII fallback for old clients and a UTF-8 `filename*` for everything
    since about 2012.
    """
    from urllib.parse import quote
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = ascii_name.replace('"', "").strip() or "download"
    disposition = (f'attachment; filename="{ascii_name}"; '
                   f"filename*=UTF-8''{quote(filename)}")
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": disposition})


def _stem(plot: Dict[str, Any]) -> str:
    return "".join(c for c in str(plot.get("show", "plot")) if c.isalnum() or c in " -_").strip() or "plot"


@app.post("/export/schedule")
def export_schedule(req: ExportRequest) -> Response:
    """Instrument schedule, by position and unit — hanging order."""
    return _attach(exports.schedule_csv(req.plot).encode(), "text/csv",
                   f"{_stem(req.plot)} — Instrument Schedule.csv")


@app.post("/export/hookup")
def export_hookup(req: ExportRequest) -> Response:
    """Channel hookup, by channel — what the board sees."""
    return _attach(exports.hookup_csv(req.plot).encode(), "text/csv",
                   f"{_stem(req.plot)} — Channel Hookup.csv")


@app.post("/export/eos")
def export_eos(req: ExportRequest) -> Response:
    """USITT ASCII patch. ⚠ Unverified format — the file says so in its header."""
    return _attach(exports.eos_patch(req.plot).encode(), "text/plain",
                   f"{_stem(req.plot)} — Patch.asc")


@app.post("/export/magic-sheet")
def export_magic_sheet(req: ExportRequest) -> Dict[str, Any]:
    """Channels grouped by purpose. JSON — the front end lays it out."""
    return {"groups": exports.magic_sheet_rows(req.plot)}


@app.post("/export/pdf")
def export_pdf(req: ExportRequest) -> Response:
    """The plot, to architectural scale, with a scale bar and a 1-inch check.

    ⚠ If the drawing will not fit the sheet at the requested scale, this fails
    with the scale that would fit rather than returning a clipped drawing. A
    plot that runs off the page looks finished and is not.
    """
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "plot.pdf")
        sheet, _ = exports.plot_pdf(req.plot, pdf, scale=req.scale,
                                    page=req.page, landscape=req.landscape,
                                    show_pools=req.showPools,
                                    show_focus=req.showFocus,
                                    show_labels=req.showLabels,
                                    pool_plane=req.poolPlane,
                                    rulers=req.rulers)
        # ⚠ Refuse only what makes the drawing WRONG. A clipped sheet is
        # unusable, so it is a 422. Everything else — a grazing pool, an
        # unrecognised accessory — is a true note ABOUT the plot, and refusing
        # to draw over it would mean a rig with one flat side light could never
        # be exported at all. They travel back in a header instead.
        fatal = [w for w in sheet.warnings if w.startswith("CLIPPED")]
        if fatal:
            raise HTTPException(status_code=422, detail=fatal[0])
        notes = [w for w in sheet.warnings if not w.startswith("CLIPPED")]
        body = open(pdf, "rb").read()
    r = _attach(body, "application/pdf", f"{_stem(req.plot)} — Plot.pdf")
    if notes:
        # latin-1 only in a header, and one line — the full text is in the logs.
        r.headers["X-Plot-Notes"] = " | ".join(notes)[:900].encode(
            "ascii", "replace").decode("ascii")
    return r


@app.post("/export/dxf")
def export_dxf(req: ExportRequest) -> Response:
    """The plot as layered DXF in feet — for a rented Vectorworks month."""
    with tempfile.TemporaryDirectory() as d:
        pdf, dxf = os.path.join(d, "p.pdf"), os.path.join(d, "p.dxf")
        exports.plot_pdf(req.plot, pdf, dxf_path=dxf, scale=req.scale,
                         page=req.page, landscape=req.landscape)
        body = open(dxf, "rb").read()
    return _attach(body, "application/dxf", f"{_stem(req.plot)}.dxf")


# ----------------------------------------------------------------- import

@app.post("/import/dxf/layers")
async def import_dxf_layers(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Layer names, counts and the declared units — so the user picks before importing.

    ⚠ Unit headers lie. Check the extents against a dimension that is known
    before trusting the file.
    """
    return await _with_temp_dxf(file, dxf_bridge.list_layers)


@app.post("/import/dxf")
async def import_dxf(
    file: UploadFile = File(...),
    layers: Optional[str] = Form(None),
    units: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """A venue's ground plan as polylines in feet, ready to draw underneath.

    layers: comma-separated names, or omitted for all.
    units:  in | ft | mm | cm | m — overrides the file header, which is often wrong.
    """
    chosen = [s.strip() for s in layers.split(",")] if layers else None
    return await _with_temp_dxf(
        file, lambda p: dxf_bridge.to_paths(p, layers=chosen, units=units))


async def _with_temp(file: UploadFile, suffix: str, fn):
    """Write an upload to a temporary file, hand it to `fn`, clean up.

    ⚠ The suffix matters: fitz and ezdxf both sniff the extension, and a PDF
    written to in.dxf is refused for the wrong reason.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    kind = suffix.lstrip(".").upper()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "in" + suffix)
        with open(path, "wb") as fh:
            fh.write(data)
        try:
            return fn(path)
        except HTTPException:
            raise                       # already said what was wrong
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"cannot read that {kind}: {e}")


async def _with_temp_dxf(file: UploadFile, fn):
    return await _with_temp(file, ".dxf", fn)


# ----------------------------------------------------------------- symbols

class RenumberRequest(BaseModel):
    instruments: List[Dict[str, Any]]
    position: Dict[str, Any]
    start: int = 1


@app.post("/import/pdf/pages")
async def import_pdf_pages(file: UploadFile = File(...)) -> Dict[str, Any]:
    """What is in a PDF, so the reader can choose a page — and find out whether
    there is any geometry in it at all.

    ⚠ `items` is a count of VECTOR items. A scanned plan has none, and no scale
    arithmetic will get walls out of a photograph of a drawing.
    """
    return await _with_temp(file, ".pdf",
                            lambda p: {"pages": pdf_bridge.pages(p),
                                       "scales": list(pdf_bridge.SCALES)})


@app.post("/import/pdf")
async def import_pdf(
    file: UploadFile = File(...),
    page: int = Form(1),
    scale: str = Form("1/4"),
) -> Dict[str, Any]:
    """A venue's ground plan out of a PDF, as polylines in feet.

    ⚠ THE SCALE IS NOT IN THE FILE. A PDF measures paper, not building — its
    coordinates are points, 72 to the printed inch — so the drawing's scale has
    to come from whoever read it off the title block. Wrong by a factor of two
    and the result is a perfectly plausible drawing of a different room, which
    is why the reply carries the extents it arrived at.
    """
    def run(path):
        try:
            return pdf_bridge.paths(path, page=page, scale=scale)
        except KeyError:
            raise HTTPException(status_code=400, detail=(
                f"{scale!r} is not a scale I know — one of "
                f"{', '.join(pdf_bridge.SCALES)}"))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return await _with_temp(file, ".pdf", run)


@app.post("/renumber")
def renumber(req: RenumberRequest) -> Dict[str, Any]:
    """Renumber the units on ONE position, per RP-2 §2.3.2.

    Stage left to stage right on a batten; top to bottom then downstage to
    upstage on a boom; nearest the plaster line on an FOH position parallel to
    centreline; nearest centreline on a box boom with real extent. `numberFrom`
    on the position overrides all of it.

    ⚠ It returns the renumbered instruments — it does NOT decide to apply them.
    On a plot that has been hung, a renumber produces a different document from
    the one taped to the pipe, so the caller has to mean it. `describe` says in
    words which convention was used, because a reader cannot tell 1-to-6 from
    6-to-1 by looking at a single number.
    """
    import copy
    insts = copy.deepcopy(req.instruments)
    before = {id(i): i.get("unit") for i in insts}
    count, warning = P.number(insts, req.position, start=req.start)
    changed = [
        {"from": before[id(i)], "to": i.get("unit"),
         "x": i.get("x"), "y": i.get("y"), "height": i.get("height")}
        for i in insts if before[id(i)] != i.get("unit")
    ]
    return {"instruments": insts, "count": count, "changed": len(changed),
            "moves": changed, "convention": P.describe(req.position),
            "warning": warning}


def _prims_json(shape) -> List[Dict[str, Any]]:
    """RP-2 primitives as JSON. Shared by /symbols and /booms so a new primitive
    kind cannot reach one drawing and not the other."""
    prims: List[Dict[str, Any]] = []
    for p in shape:
        if p[0] == "poly":
            prims.append({"k": "poly", "pts": [[round(a, 4), round(c, 4)] for a, c in p[1]],
                          "closed": bool(p[2])})
        elif p[0] == "line":
            prims.append({"k": "line", "a": [round(v, 4) for v in p[1]],
                          "b": [round(v, 4) for v in p[2]]})
        elif p[0] == "circle":
            style = p[3] if len(p) > 3 else None
            prims.append({"k": "circle", "c": [round(v, 4) for v in p[1]],
                          "r": round(p[2], 4),
                          "dashed": style == "dashed", "filled": style is True})
        elif p[0] == "text":
            prims.append({"k": "text", "c": [round(v, 4) for v in p[1]],
                          "s": p[2], "size": p[3]})
    return prims


@app.get("/symbols")
def symbol_geometry(types: str, lens_rotation: Optional[float] = None) -> Dict[str, Any]:
    """RP-2 symbol outlines for a comma-separated list of fixture types.

    ⭐ The geometry lives in ONE place — symbols.py — and both the PDF and the
    browser draw from it. Porting the shapes to TypeScript would guarantee the
    two drift, and `test_agreement.py` exists precisely to stop that happening
    with numbers; the same argument applies to shapes.

    Local coordinates, in feet: +a is toward the back of the instrument, -a the
    front, c is across. The origin is the yoke — the hanging point.

    An entry may carry accessories after a pipe: `S4 26|top hat+gobo`. The key
    in the reply is the WHOLE entry, so the browser looks a symbol up by the
    same string it asked for and two units of one type with different
    accessories stay distinct. Unknown accessories come back in `warnings`
    rather than being dropped — a barn door nobody drew is a barn door nobody
    hangs.
    """
    out: Dict[str, Any] = {}
    warnings: List[str] = []
    for t in [x.strip() for x in types.split(",") if x.strip()]:
        base, _, acc_s = t.partition("|")
        acc = [a.strip() for a in acc_s.split("+") if a.strip()]
        shape = sym.for_type(base.strip(), lens_rotation)
        if acc:
            shape, unknown = sym.with_accessories(shape, acc)
            warnings += [f"{base.strip()}: {u}" for u in unknown]
        out[t] = _prims_json(shape)
    return {"symbols": out, "warnings": warnings,
            "source": "USITT RP-2 (2006), plates pp.4-9"}


# ----------------------------------------------------------------- plots on disk

class SaveRequest(BaseModel):
    name: str
    plot: Dict[str, Any]


@app.get("/plots")
def list_plots() -> Dict[str, Any]:
    """Every plot in the plots folder, newest first."""
    return {"plots": plotstore.listing(), "folder": str(plotstore.root())}


@app.get("/plots/{name}")
def read_plot(name: str) -> Dict[str, Any]:
    try:
        return {"name": name, "plot": plotstore.read(name)}
    # 🔴 JSONDecodeError FIRST. It is a subclass of ValueError, so catching
    # ValueError above it swallowed every parse failure and left this branch
    # unreachable — a corrupt plot answered 400 with a bare "Expecting value:
    # line 1 column 1", which names neither the file nor what to do about it.
    # Caught by pylint's bad-except-order in CI, not by any test, because every
    # test opened a file that parsed.
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"{name} will not parse: {e}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"no plot called {name}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/save")
def save_plot(req: SaveRequest) -> Dict[str, Any]:
    """Write a plot to disk, overwriting it.

    ⭐ Jerry, 2026.09.24: "the save is not automatically overwriting the file —
    it tries a new name Without Consent.plot (1).json." That bracket is the
    browser's DOWNLOAD behaviour: Save was built on the File System Access API,
    which only Chrome and Edge have, so everywhere else every press left another
    copy in Downloads. The server has a filesystem; it does the writing now, in
    every browser, by the same code.

    ⚠ The name is a NAME. It is written in the plots folder and nowhere else —
    see store.resolve(), which checks the spelling AND checks the resolved path
    is still inside that folder.
    """
    try:
        path = plotstore.write(req.name, req.plot)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        # ⚠ Never a silent success. A save that did not happen and says nothing
        # is how a day of work goes missing.
        raise HTTPException(status_code=500, detail=f"could not write {req.name}: {e}")
    return {"name": path.name, "path": str(path), "bytes": path.stat().st_size}


# ----------------------------------------------------------------- booms

class BoomRequest(BaseModel):
    positions: List[Dict[str, Any]]
    instruments: List[Dict[str, Any]]
    # ⚠ Formatting only. The heights are feet either way; this decides how the
    # LABEL beside each unit is written. Without it a metric plot showed its
    # boom heights in feet and inches on screen while the paper said metres.
    units: Optional[str] = None


@app.post("/booms")
def boom_layout(req: BoomRequest) -> Dict[str, Any]:
    """RP-2 §6.12 boom elevations: where each unit is DRAWN, beside the plot.

    ⭐ In plan a boom is a POINT — every unit on it shares one x and y and
    differs only in height. Drawing them there stacks them on top of each other,
    which is what the browser used to do. The readable layout goes beside the
    plot, and this says where.

    ⚠ The arithmetic is booms.py, the same call scaled_pdf.boom_elevation()
    makes. Retyping the compression in TypeScript is how the screen and the
    paper drifted three times in one week.

    `dy` is feet above the elevation's base. `height` and its `label` are the
    REAL trim and are never compressed — the break marks say the paper is
    short, never that a number is approximate.
    """
    from . import units as _u
    out = booms.layout(req.positions, req.instruments,
                       system=_u.system_of({"units": req.units}))
    for b in out:
        # §6.12: "hatch or shade acceptable for top view of boom." ONE symbol
        # standing for the stack — four drawn on top of each other is a blob.
        shape = sym.for_type(b["plan"]["type"])
        b["plan"]["prims"] = _prims_json(shape)
        b["plan"]["hatch"] = _prims_json(sym.hatch(shape))
        # ⚠ Each unit carries its OWN outline, accessories included. The browser
        # keys its symbol cache by "type|accessories"; looking an elevation up by
        # the bare type would quietly draw a unit without its top hat, or fall
        # back to a plain ring when the cache had no bare-type entry at all.
        for u in b["units"]:
            us = sym.for_type(u["type"])
            if u.get("accessories"):
                us, _ = sym.with_accessories(us, u["accessories"])
            u["prims"] = _prims_json(us)
    return {"booms": out,
            "pitch": booms.BOOM_PITCH,
            "space": booms.space_needed(req.positions, req.instruments),
            "source": "USITT RP-2 (2006) 6.12, Option 1"}


# ----------------------------------------------------------------- labels

class LabelRequest(BaseModel):
    positions: List[Dict[str, Any]]
    instruments: List[Dict[str, Any]]
    room_width: Optional[float] = None
    # The drawable area in plot feet, (x0, y0, x1, y1). The browser's canvas is
    # sized to what it draws, so it normally has none — but pass it if there is
    # one, or a name can be fitted somewhere that is not on the page.
    bounds: Optional[List[float]] = None
    # Feet per CHARACTER at the browser's own label size. Text metrics belong to
    # whoever is drawing: ReportLab measures Helvetica, the browser measures
    # whatever the system gave it, and neither can measure for the other.
    char_w: float = 0.26
    text_h: float = 0.42
    # Formatting only: a position label carries its trim.
    units: Optional[str] = None


@app.post("/labels")
def label_layout(req: LabelRequest) -> Dict[str, Any]:
    """Where each position's NAME goes, fitted around the units and each other.

    ⭐ RP-2 §2.1 wants every position identified but does not say where the name
    sits — on a drawing that is a fitting problem. Placed one at a time at the
    pipe's stage-left end, `CAT 1  (FOH)` and `HOUSE LEFT BOX BOOM 1` landed on
    top of each other and both across the box boom's symbol.

    ⚠ The RULE is labels.py, the same call plot_to_pdf makes, so the screen and
    the paper choose the same slot. Only the width measurement differs, because
    it has to.
    """
    from . import units as _u
    out = lbl.plan(req.positions, req.instruments,
                   lambda t: len(t) * req.char_w,
                   room_width=req.room_width, text_h=req.text_h,
                   system=_u.system_of({"units": req.units}),
                   bounds=tuple(req.bounds) if req.bounds else None)
    return {"labels": out, "source": "USITT RP-2 (2006) 2.1"}


# ----------------------------------------------------------------- names

class NamesRequest(BaseModel):
    names: List[str]


@app.post("/resolve-names")
def resolve_names(req: NamesRequest) -> Dict[str, Any]:
    """Map instrument names from paperwork to photometric table keys.

    Lightwright says `ETC Source4 36deg`; the table says `S4 36`. Before this
    existed, an imported plot drew correctly and was silently unlit — 81% of the
    names in the real archive needed translating. Anything that cannot be
    resolved comes back with a REASON, never a blank.
    """
    ok, bad = fixture_names.audit(req.names, ph.FIXTURES)
    return {"resolved": ok, "unresolved": bad,
            "counts": {"resolved": len(ok), "unresolved": len(bad)}}
