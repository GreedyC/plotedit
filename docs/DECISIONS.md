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


## 2026.09.29 — "Changed" means it differs from disk, not that you touched it

Jerry asked it as a philosophical question: *"if someone selects a light and does
nothing to it, should the plot be considered changed?"*

**No — and the test is simple: if it isn't saved, it can't be unsaved.** Selection
is not in the `.plot.json` at all, so there is no state on disk for it to differ
from. Nothing you do that the file cannot record may set the dirty flag.

Selecting was already clean. The same test applied one layer down was not:

- **Writing a field back the way it was marked the plot changed.** Type `R5` into
  the colour box, type `R52+R119` back, and the badge came on for a net change of
  nothing. (Found on 2026.09.29 while testing the gel combo.)
- **It also pushed a dead undo step** — press undo, nothing moves, press again —
  and **threw away the redo stack** on the way past.
- **Undoing back to the saved state stayed dirty.** You could return the document
  to exactly what was on disk and still be warned you had something to lose.

So `_dirty` was a flag for *activity*. It is now a comparison: `_seq` counts real
changes, `_savedSeq` remembers where the file was written, and `dirty` is
`_seq !== _savedSeq`. Undo and redo carry the revision back with the plot, which
is what makes stepping back to the save point go clean. `update()` compares its
patch first and, if nothing is new, unwinds the `begin()` that preceded it.

**⚠ Why this is worth the code rather than a shrug.** A false "unsaved changes"
is not cosmetic — it teaches you the discard prompt is noise, and you start
clicking through it. The one evening it is real, you lose a tech session. The
badge is worth exactly as much as its false-positive rate.

**⭐ The precedent is dimmer-versus-address** (2026.09.28): the rule was enforced
once, in one reader, with the tie-break written down, and nothing was hidden from
the user. Same shape here — the store decides, and no caller has to remember.

Selection remains view state everywhere except `snapshot()`, which captures it on
purpose so undo puts your eye back on the unit that changed. That is a kindness,
not a claim that selection is document state.

## 2026.09.29 — A dimmer is a DMX personality, and a house can say so

Jerry: *"in ETC world, a Dimmer is a DMX shape — basically one address with the
value of intensity."*

So it is a **personality**, not a model — the dimmer is not the fixture, it is
what the fixture is plugged into. `dmx.UNIVERSAL` holds it, it belongs to no
entry in `MODELS`, and it is offered to any unit.

**This was already the behaviour; what changed is that it can now be said.**
`patch_cell` has always fallen through to *"a conventional fixture is one
address"* with a footprint of 1. 🔴 But that sentence was also what a unit got
when **nobody had recorded a profile at all** — same number, same words, for a
decision and for a silence. Naming the personality separates them, and
`patch_cell` now answers a recorded `Dimmer` before it looks anything up.

A fourth control model, **`dimmer-is-address`**, says the house works this way.
In it:

- The **personality list offers `Dimmer`** — which is also what finally fills the
  gap in `MUTUALLY-EXCLUSIVE-FIELDS.md` §1.3, where a Source Four's personality
  dropdown was permanently empty.
- The **hexagon carries the address** and the rectangle the circuit, exactly as
  for an LED. ⭐ A mixed rig then reads the same throughout: the reader stops
  having to know which kind of unit they are looking at to read the number.
- `circuits.check` gains the matching contradiction — a dimmer and an address
  that disagree. ⚠ Compared on the bare number, because `45` and `1/45` are the
  same fact written two ways.

**⚠ A unit with a dimmer and no address still draws its dimmer.** The house being
addressable does not mean every unit's address was recorded.

## 2026.09.29 — Fields that do not apply go inert, not hidden

Jerry: *"lets try having unused fields greyed-out (inert)"* — answering the open
question in `MUTUALLY-EXCLUSIVE-FIELDS.md`.

A row that vanishes takes its explanation with it and changes the panel's shape
under the cursor. A greyed row **keeps its place, keeps its value, and says why
on hover**. Six rules, all reading the server's tables rather than a list of
names typed into the browser:

| Field | Inert when |
|---|---|
| Lamp | the fixture has output modes — it is an LED engine |
| LED mode | it has none — it takes a lamp |
| Dimmer | the unit is patched as `Dimmer`, or the house is dimmer-is-address and it has an address |
| Lens angle | it is not an oval-beam unit |
| Model | no models are on file for the type |
| DMX personality | no personalities are published for it |

**🔴 Inert disables input; it does not filter data.** A unit already carrying a
contradictory value still shows it, greyed — `sample.plot.json`'s `Lustr 26 EDLT`
displays its stray `HPL 575` rather than swallowing it. **Hiding a wrong value is
how it survives to the load-in.** Same reasoning as the dirty flag above: a
hidden field holding a live value is the worst of the three options.

⭐ **And the arithmetic was already safe, checked rather than assumed:** a Lustr
computes the same footcandles with or without a stray lamp, and a Source Four the
same with or without a stray mode. The value that does not apply is ignored in
both directions, so nothing had to be cleared to make this safe.
