# Decisions

Short entries. What was decided, when, and why — so it is not re-argued.

## 2026.09.23 — A plot editor, not a CAD program

Vectorworks is a general platform: walls, stairs, 3D solids, a plant database.
Building a "simple version" means building 95% of it to use 5%. **Scope is a light
plot and its paperwork.** Architecture arrives as DXF and is never drawn here.

## 2026.09.23 — TypeScript over Python, not Rust

The original thought was Rust. Set aside because:

- No Rust toolchain on the machine; Node 22 and .NET 7 are installed.
- The computation half is already written and tested in Python.
- What is missing is **interaction**, which is a front-end problem.
- It has to run at tech on a laptop with no internet — a local server and a
  browser tab is the least fragile way.

**Rust remains legitimate as a second version once the shape is proven.** It was
set aside because the goal is the tool.

## 2026.09.23 — The file format is plain JSON

One `.plot.json` per show. Readable, diffable, git-able, and openable without a
subscription. This is a direct response to two shows in the designer's archive
being locked inside `.vwx` files nothing can read.

## 2026.09.23 — Field names follow the Vectorworks/Lightwright exchange

`position · unit · channel · dimmer · address · universe · type · wattage · color ·
gobo · purpose · focus · trim · accessory · notes`. Using the names the industry
already uses means `paperwork.py` imports old shows with no translation layer.

## 2026.09.23 — SVG, not canvas

A 60-unit plot is small either way. SVG is easier to get right, and every
instrument becomes a DOM node — which is hit testing for free when step 4 needs
dragging. Revisit only if a plot ever gets large enough to feel slow.

## 2026.09.23 — Screen scale and paper scale are different things

Pixels per foot on screen; ¼" = 1'-0" on paper. The screen zooms, the paper must
measure true. `geometry.ts` holds the first, `scaled_pdf.py` the second, and
`test_agreement.py` checks they agree about the numbers even though they differ
about the units.

## 2026.09.23 — Snapshot undo, and a drag is one step

A plot is a few dozen instruments, so history is an array of deep clones. Edits
sharing a coalesce key merge into one entry, which is what makes a drag undo in
one go rather than two hundred.

## 2026.09.23 — Instruments snap to pipes

Units hang on pipes. A unit at y = 20.3 when the pipe is at 20 is wrong on paper
and wrong in the room, and it is invisible until the plot is printed. Snapping
also sets the instrument's `position`, so the schedule stays true without anyone
retyping it. Alt-drag opts out. Dragging far past the end of a pipe does not snap.

## 2026.09.23 — Exports refuse rather than clip

`/export/pdf` returns 422 with the sheet's own warning when the drawing will not
fit, and the front end shows it. A clipped plot looks finished and is not — the
same rule the drawing code has had since it was written.

## 2026.09.23 — The Eos patch ships with its own warning

No real Eos patch export was available to reverse-engineer from, so the format
follows the spec and nothing else. The warning is in the file's header rather
than only in the docs, because the file is what somebody will open at tech.

## Open

- **Symbols.** ✅ Settled as a question, open as work. The standard is **USITT RP-2
  (2006)**, in `docs/reference/` — Jerry has the same file, verified identical.
  **The current symbols are not RP-2**; `docs/SYMBOLS.md` lists every difference
  and the order to fix them in. RP-2 also covers **movers (§6.8), LED fixtures
  (§6.16), the hexagon/rectangle/circle notation (§6.14) and three line weights
  (§6.18)** — all of which the editor currently ignores.

- **The Eos patch format.** Written to spec, never tested. Ten minutes with
  Nomad and a scratch show file settles it.

## 2026.09.26 — Fixtures arrive as code, not as imported SVG

Testers asked whether a fixture plotedit does not draw could be supplied as an
SVG file. **No — they are contributed through a fork instead**, and the standard
for doing it is the longest section of `CONTRIBUTING.md`.

Three reasons, in the order they matter:

- **An SVG is not a symbol.** A plot symbol carries a real size in feet, an
  origin at the yoke — which is what it rotates about — a facing, and line
  weights from the three RP-2 §6.18 allows. A drawing file has a bounding box
  and pixel strokes. Every one of those four would have to be asked for
  separately, and a wrong yoke puts every focus angle quietly out.
- **The geometry lives in one place.** `symbols.py` feeds both the PDF and the
  browser through `GET /symbols`. `docs/SYMBOLS.md` says porting the shapes to
  TypeScript would guarantee they drift; a second runtime source of shapes is
  the same mistake wearing a different hat.
- **SVG is XML, and this is a local server** that people would feed files from
  the internet. Entity expansion, external references, embedded script. That is
  a real exposure for a feature whose whole job is to draw a light.

**⭐ The objection this answers is "a fork is slow".** It is not: the symbol works
on your own plots the moment you write it, and the pull request is only how it
reaches everyone else. Nobody waits on review to draft a show.

**⚠ And there is a cheaper route that is not a new symbol at all** — mapping an
unrecognised fixture onto an existing RP-2 family in `fixture_names.py`, which is
one line and no geometry. Most people asking for a custom symbol want their
unfamiliar unit to stop being a blank, not to draw one. That route is offered
first in `CONTRIBUTING.md`.

Revisit if a standards-correct symbol library ever exists in a form worth
importing wholesale. Arbitrary user artwork in an RP-2 plot is what is refused
here, not interchange.

