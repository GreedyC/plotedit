# Light plot editor — spec

**Decided 2026.09.23.** Jerry asked whether to write "a simple version of Vectorworks," probably in Rust. **Conclusion: build a light plot editor, not a CAD platform, and build it in TypeScript over the Python that already exists.** *(Asked which mattered more, the tool or the Rust: **"the tool."**)*

**Where it lives:** a new repo in `~/Projects/`, built with Claude Code in VS Code. **Not in My AI Brain** — this folder is business context and client work, not a source tree.

---

## What it is

**A tool for drawing a light plot and producing the paperwork.** One job, done properly.

## What it is not

**Not a CAD program.** No walls, no stairs, no 3D solids, no plant database. Vectorworks is a general platform and you would build 95% of it to use 5%. **The ground plan comes in as DXF; the editor never draws architecture.**

---

## Why TypeScript and not Rust

| | |
|---|---|
| **Rust is not installed** | No `cargo`, no `rustc`. Node 22 and .NET 7 are. |
| **Half the work is already done in Python** | `my-skills/plot/` has scale, sheets, photometrics, gel transmission, wash spacing, sections, DXF in and out. Rewriting it in Rust buys nothing. |
| **What is missing is interaction** | Clicking and dragging instead of editing a script. That is a front-end problem. |
| **It has to run at tech** | On the laptop, beside Nomad, with no internet. A local server and a browser tab is the least fragile way to do that. |

**⚠ If Rust ever becomes the goal for its own sake, that is a legitimate but different project.** Prove the shape first.

---

## Architecture

```
  browser (TypeScript, canvas or SVG)   <-- drag, click, edit
        |  JSON over localhost
  Python service (FastAPI)              <-- the existing my-skills/plot code
        |
  photometrics.py · scaled_pdf.py · dxf_bridge.py · paperwork.py
```

**Run it with one command; it opens a browser tab. No install, no account, no network.**

### The file format is plain JSON

**One `.plot.json` per show**, human-readable and diffable, versioned in git beside the production notes. **That is a real advantage over `.vwx`** — see the archive inventory: *She Loves Me* and *Drood* are locked inside files nothing can open. **A plot Jerry can read in a text editor in twenty years is worth more than one that needs a subscription.**

### The instrument record

Take the field names already in use — they come from the Vectorworks/Lightwright exchange and map straight to `paperwork.py`:

`position · unit · channel · dimmer · address · universe · type · wattage · color · gobo · purpose · focus (x,y,h) · trim · accessory · notes`

---

## v1 — what must work

1. **Import a DXF ground plan** as the base drawing. *(`dxf_bridge.import_into` already does this.)*
2. **Place instruments** from a symbol library, drag to position, rotate to focus.
3. **Edit the data** — channel, color, purpose, type — in a table beside the drawing, both views live on the same record.
4. **Show the light.** Field and beam pools at head height, throw, elevation, footcandles through gel. *(`photometrics.py` already computes all of it.)*
5. **Export:** plot PDF to scale *(`scaled_pdf.py`)*, instrument schedule and channel hookup, DXF, and **Eos ASCII patch** *(`make-eos-asc.py`)*.

## Later, not v1

Section view · magic sheet · focus charts · circuit and load tracking *(Art's job)* · multi-universe patch · revision compare · reading `.lw6` directly.

## Explicitly never

3D rendering · pre-visualization · anything Capture does better · anything a venue expects in `.vwx`.

---

## ⭐ Is it core? — answers, so the question stops being re-argued

**Jerry, 2026.10.13.** `CLAUDE.md` says every unasked-for feature gets put to him
with the same question — *is this a core part of the app?* — and that the answer
is usually no. The ones below have been asked and answered, and this is where to
look before asking again.

| | | |
|---|---|---|
| **Layers**, user-defined | ✅ **CORE** | *"layers are core, just a matter of when"*. ⚠ **Conditional: they must not slow the drawing down.** A plot redraws on every drag; a layer system that costs frames costs the thing the app is for. The derived purpose layers shipped 2026.10.13 (#132); the explicit half is #108. |
| **Importing a set** | 🟡 **maybe, later** | *"importing 3D sets from other sources might be nice."* See the note below on what that should actually mean. |
| **Instrument weight** | ❌ not core | |
| **Cabling** | ❌ not core | Art's job, like circuit and load tracking above. |
| **Sets / scenery as objects** | ❌ not core | The set is somebody else's drawing. What the section needs from it is a profile, not a model. |
| **Multiple views, CAD-style** | ❌ **out of scope** | Plan and section are two drawings, not two viewports. A tiled multi-view editor is the shape of the tool this one exists to avoid. |

### ⚠ "Importing a set" should probably not mean 3D

**DXF is a 3D format** — every point carries X, Y **and Z**, and it has true 3D
entities (`3DFACE`, `3DSOLID`, `MESH`, 3D `POLYLINE`). ⚠ **`dxf_bridge.py` is
strictly 2D**: it reads `LINE`, `CIRCLE`, `ARC`, `ELLIPSE`, `SPLINE`,
`LWPOLYLINE`, `POLYLINE` and `INSERT`, and **discards Z on every one**. A set
model dropped in today imports as nothing, or as flattened spaghetti.

🔴 **And the useful question is 2D anyway.** What the section needs from a set is
its **profile at the cut line** — enough to see whether a beam clears it. Every
section this app prints already says so:

> *"Scenery in section — ask the set designer. Until then: no obstruction is
> checked; a beam may be blocked."*

A set designer's section is a flat DXF. **The plan already underlays an imported
ground plan; the section underlays nothing** — `plot_to_section.render()` takes
no `base` at all. ⭐ **That is the cheap version of this feature and most of its
value**, and it does not need a Z-aware importer, a cutting plane, or a view that
is not a plan — all of which run straight into "multiple views, CAD-style" above.

---

## The symbols question

**Jerry's own convention is Field Template / SoftSymbols for ETC, with AutoPlot for cable and truss** *(found 2026.09.22 on the external drives)*. Those are `.vwx` and cannot be reused. **The editor needs its own symbol set drawn to USITT RP-2**, which `scaled_pdf.py` already has a first pass at. **Ask Jerry to mark up that draft sheet before any more are drawn.**

---

## Why this is worth building at all

**Vectorworks is now subscription-only and Lightwright has followed.** A designer doing small shows pays a professional-tier subscription to draw ten units on a pipe. **The tools exist for large productions and nobody serves the small room** — which is most of the work, and all of Jerry's current work.

**⚠ Do not let that become a product plan.** Build it because Jerry needs it in November at the Drake. If it turns out others want it, that is a decision for later and a different document.
