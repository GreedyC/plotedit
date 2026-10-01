# Next

In order. Each step should leave something that runs.

➡ **Layers have their own plan:** [`LAYERS.md`](LAYERS.md), written for #82. ⚠ Its
finding is that the app **already has layers, in two incompatible schemes**, and
neither is the one #82 describes — so the work is choosing between three answers,
not adding a missing one. Nothing in it is built.

➡ **The menus and toolbars had their own plan, and most of it is built:**
[`MENUS-AND-MATERIAL.md`](MENUS-AND-MATERIAL.md), written for #56 and delivered
in #77 the same day. It measures what was inconsistent, works out what Material
Design 3 actually requires, and records why each control ended up the shape it
is. ⚠ Kept as reasoning rather than as a to-do — but **two of its eight steps
did not land**, and they are named at the top of it along with the open questions.

## 1. Make the Python importable as a package ✅ done 2026.09.23

- `scaled_pdf.py` now uses relative imports for `photometrics` and `dxf_bridge`.
- `make-eos-asc.py` renamed **`eos_ascii.py`** — a hyphen cannot be imported — and
  turned from a script with module-level constants into `build(show, groups, cues)`.
  The *Without Consent* data is kept as `EXAMPLE_*` and still prints via
  `python3 -m plotedit.eos_ascii`.
- `gels.csv` resolves off `__file__`, so it survived the move unchanged.
- `server/test_package.py` added — a smoke test, not a unit suite.

**🔴 It found a real bug, which is why this step exists.** `Sheet.unit()` tested
`color_gel.upper() in ph.GELS`, a plain dict lookup, so any compound notation
missed and **silently fell back to open white**. `R52+R119` — the acting-area wash,
the most common color in the archive — reported **729 fc instead of 169**. Fixed
here and in `My AI Brain/my-skills/plot/`, and the test now pins the value.

**Run it:** `cd server && python3 test_package.py`

## 2. A read-only service ✅ done 2026.09.23

`server/plotedit/api.py`. Six endpoints, nothing that writes:

| | |
|---|---|
| `GET /health` | fixture and gel counts |
| `GET /fixtures` | all 28, with beam/field, penumbra, candela, modes **and source** |
| `GET /gels` | all 11, with transmission and source, plus what `+` and `/` mean |
| `POST /compute` | instruments in; throw, elevation, pan, pools, footcandles out |
| `POST /wash` | field-to-beam spacing, and how many units cover a width |
| `GET /lens` | which barrel gives the pool you want at that throw |

**Run it:** `cd server && uvicorn plotedit.api:app --reload`
**Test it:** `cd server && python3 test_api.py` *(TestClient — no server needed)*

### Two decisions worth keeping

**Sources travel with the numbers.** `/fixtures` returns `"ETC S4 LED Photometry
Guide p7: Series 2 Lustr 26° EDLT"` alongside the candela. Strip that and the front
end has no way to show that a Lustr figure is EDLT-only — which is exactly the
mistake that had to be corrected once already.

**The API refuses rather than guesses.** No trim or focus → `computed: false` and
a reason. Unknown fixture → the same. Unknown gel → the level is returned but
flagged as open white. A fixture with no published beam angle → HTTP 400 quoting
the manual. **A missing number must never arrive looking like a real one.**

### CORS is localhost only

This runs on the designer's laptop at tech, not on a network. Origins are pinned
to the Vite dev server.

## 3. A drawing surface that renders a plot it cannot edit ✅ done 2026.09.23

Vite + TypeScript, SVG, no interaction yet.

| File | |
|---|---|
| `web/src/geometry.ts` | the transform, with its own test — `npm test` |
| `web/src/plot.ts` | the `.plot.json` types |
| `web/src/render.ts` | SVG drawing: room, positions, symbols, focus, pools, USITT annotation |
| `web/src/api.ts` | talks to the Python |
| `web/src/main.ts` | loads the sample, computes, draws, fills the schedule |
| `server/testdata/blackbox.plot.json` | ten instruments in the test room |
| `server/plot_to_pdf.py` | the same file through `scaled_pdf` — the start of step 5 |

**Run it:** `cd server && uvicorn plotedit.api:app` and `cd web && npm run dev`

### Decisions

**SVG, not canvas.** A 60-unit plot is small either way, SVG is easier to get right,
and every instrument is a DOM node — which is hit testing for free in step 4.

**Everything inside the root `<g>` is drawn in real feet.** The group transform
carries the scale and the y flip, so the markup reads in the units of the room.
Text needs `counterFlip()`.

**Screen scale is pixels per foot, not an architectural scale.** ¼" = 1'-0"
belongs to paper and stays in `scaled_pdf.py`. On screen it zooms; on paper it
must measure true. Keep the two apart.

### 🔴 It found the second real bug

`scaled_pdf.unit()` had **no `mode` parameter**, so an LED fixture was computed at
its reference output no matter what the plot asked for. The Lustr units read
**441 fc on paper and 382 on screen** — the same rig, disagreeing, because
"Regulated 3200K" never reached the function. Fixed in both copies.

**`server/test_agreement.py` now pins it:** both paths start from the same
`.plot.json` and every throw, pool and footcandle must match.

## 4. Editing ✅ done 2026.09.23

| File | |
|---|---|
| `web/src/store.ts` | one plot, one selection, an undo stack, and pipe snapping. Own test: `npm run test:store` |
| `web/src/interact.ts` | pointer and keyboard — drag, select, nudge, delete, undo |
| `web/src/inspector.ts` | the selected record, editable, nineteen fields |

**Verified in the browser:** dragging unit 1 from GRID C onto GRID D re-set its
`position` by itself, and the server recomputed — throw 13'-4" → 16'-5", pool
5'-11" → 7'-4", level **179 fc → 118 fc**. One undo restored all of it and left
the stack empty. Changing a color in the inspector took unit 3 from 185 fc to
**72 fc through R80 at 9%**.

### Decisions

**A whole drag is one undo step.** `store.begin(key)` coalesces consecutive edits
sharing a key; `commit()` ends the run. Eight pointer moves, one undo.

**Snapshots are deep clones of the whole plot.** A plot is a few dozen
instruments. No diffing, no proxies, nothing to debug at two in the morning
during a tech.

**⭐ Instruments snap to pipes, and set their own `position`.** A unit at y = 20.3
when the pipe is at 20 is wrong on paper and wrong in the room, and nobody
notices until it is printed. Alt-drag places one off a pipe deliberately.
Dragging *far* past the end of a pipe does not snap back — silently yanking a
unit seven feet is worse than leaving it where it was put.

**Focus is a separate handle.** Aiming a unit and moving it are different
decisions; conflating them is how a focus gets lost while tidying a hang.

**Positions round to the nearest inch.** Sub-inch precision on a light plot is a
lie.

**Photometric fields recompute; paperwork fields do not.** Type, trim, focus,
color, lamp and mode hit the server, debounced. Purpose and notes do not — a
round trip per keystroke is noise.

**Edits commit on `change`, not `input`**, so half-typed values never reach the
server.

### Keyboard

`↑↓←→` nudge an inch · `⇧` + arrow nudges a foot · `Delete` removes ·
`Esc` deselects · `⌘Z` / `⇧⌘Z` undo and redo

## 5. Import and export ✅ done 2026.09.23

**Out** — `server/plotedit/exports.py`, offered from the toolbar:

| | |
|---|---|
| Plot PDF | architectural scale, scale bar, 1-inch check. Scale picker: ⅛ ¼ ⅜ ½ |
| Plot DXF | layered, in feet — for a rented Vectorworks month |
| Instrument schedule | CSV, by position then unit — hanging order |
| Channel hookup | CSV, by channel — what the board sees |
| Eos patch | USITT ASCII ⚠ **format unverified** |
| Magic sheet | JSON, channels grouped by purpose — no layout yet |

**In** — a venue's `.dxf` becomes the base drawing. Layers are listed first with
their counts and the declared units, the chosen ones come back as polylines in
feet, and they draw in gray under everything.

### Decisions

**A plot that will not fit FAILS with the scale that would.** `/export/pdf`
returns 422 carrying the sheet's own warning, and the front end puts it in the
status line. A clipped PDF looks finished and is not.

**The imported extents are announced.** *"imported 8 paths, 33.0' × 38.0' —
check that against something you measured."* Unit headers lie, and a venue's
drawing is their claim rather than a survey.

**🔴 The Eos patch format has never been tested against a console.** The cue
exporter was reverse-engineered from a real Eos export after three guesses
failed; no real *patch* export was available. **The warning is written into the
file's own header**, so it travels with it. Units missing a channel or an
address are listed as comments rather than dropped — a silently missing unit at
tech is worse than a noisy file.

### 🔴 It found the third real bug

`Content-Disposition` is a latin-1 header, and the export filenames carry an em
dash — *"Without Consent — Plot.pdf"*. Every download raised
`UnicodeEncodeError`. Fixed with RFC 5987: an ASCII fallback plus
`filename*=UTF-8''…`, verified present in both forms.

**Test:** `cd server && python3 test_export.py`

---

## Next, in no particular order


- **➡ THREE DRAWING BUGS MOVED TO ISSUES, 2026.09.30**, with their measurements
  intact. They were the kind that need numbers next to them, so they were written
  up here first and then moved once the repository started using issues.

  - **✅ [#57](https://github.com/jerryjonas3/plotedit/issues/57) — DONE
    2026.09.30.** `_fits` compared a SPAN against a sheet while the renderer
    placed by ORIGIN. What closed it was not `_fits` but the PLACEMENT: the
    centring added the same day made a span that fits actually fit, so the
    comparison became true. **A2, A1 and A0 are in.**
  - **[#58](https://github.com/jerryjonas3/plotedit/issues/58)** — plan labels
    are spaced in stage FEET while the text is 7pt on PAPER, so they collide as
    the scale shrinks. 0 pairs at 1/2", 1 at 1/4", 3 at 1/8".
  - **[#59](https://github.com/jerryjonas3/plotedit/issues/59)** — the clipping
    guard reserves 1.3" at the top of every sheet and nothing is ever drawn
    there. It is the whole of the remaining top gap.

  ⚠ **What stays in this file** is the reasoning that belongs beside the code —
  the notes inside `PAGES`, `slack_above()` and `plot_to_pdf` still say why, and
  they point at the same three problems. **An issue is where you decide to fix
  something; a comment is where you find out you shouldn't have removed it.**

- **🔴 NOTATING DIMMER DOUBLERS — raised by Jerry 2026.09.29, deliberately
  deferred.** The `HPL 550/77` lamp went in the same day, so a doubled rig can
  now be described *at the lamp*. **It cannot be described at the circuit**, and
  that is the half that matters.

  ETC Dimmer Doubling runs **two fixtures off one dimmer** on opposite
  half-cycles. So a doubled dimmer is a property of the CIRCUIT, not the
  instrument: two units, one dimmer, two separate control channels.

  ⚠ **Until it is notated, the paperwork is quietly wrong in three places:**

  - **The load table.** `circuits.py` totals watts per dimmer. Two doubled units
    read as 1100 W on one dimmer, which is the arithmetic but not the situation
    — and a doubler has its own capacity limit that nothing here knows about.
  - **The hookup.** Two channels sharing a dimmer is exactly the thing a hookup
    exists to show, and there is no column that can say it.
  - **The plot.** RP-2 has no symbol for it that we have found, so the notation
    may have to be Jerry's own. Worth checking §6.14 before inventing one.

  ⭐ **And the reverse mistake is the dangerous one:** a `HPL 550/77` picked on
  an ORDINARY dimmer computes perfectly reasonable footcandles and hangs a rig
  that comes out dim. Nothing can catch that until the circuit can say whether
  it is doubled.

- **✅ THE GEL LIBRARY — done 2026.09.29, except the diffusions.** 11 gels became
  **498**: 239 Roscolux and 259 LEE, each row citing the maker's own page.

  ⚠ **What is still missing is one class, and it is the same class from both
  makers: DIFFUSION.** 29 Roscolux (the R100 series — frosts, silks, spuns,
  Rolux) and 43 LEE. **Neither publishes a transmission for them on the web.**

  ⭐ **But Rosco's myColor app does.** R119, R114 and R132 are already on file at
  0.893, 0.888 and 0.901, read off that app by Jerry on 2026.09.22 — figures the
  product pages do not carry. **That is where the rest of the diffusions come
  from**, and it is a hand job rather than a fetch.

  **➡ Still open: whether a diffusion's transmission is the right number at
  all** — see the measurement below. Entering 43 more of them does not answer it.

- ~~**THE GEL LIBRARY — the cheapest large win on this list.**~~ *(Jerry,
  2026.09.28: the rest of Roscolux plus the Lee Designer's Edition "would take
  care of about 95% of the colour use I bet".)*

  **There are eleven gels on file.** Eight colours and three Hamburg frosts, in
  `server/plotedit/gels.csv`. Every footcandle through anything else refuses.

  **⭐ The work is data entry, not code.** The format is already right: one row
  per gel — number, name, transmission, **source**, date — and `parse_gel` is
  prefix-agnostic, so `L201+R119` reads correctly today without a change.

  **➡ One wording fix comes with it.** An unknown gel says *"add it with Rosco's
  transmission figure"*, which will be wrong the moment there are Lee numbers in
  the file.

  **❓ And one question worth settling while the data is in front of you: is a
  frost's transmission enough?** A colour filter absorbs, so its transmission
  scales candela uniformly and multiplying is exactly right. **A diffusion
  scatters** — it widens the field and drops the peak by more than the
  transmission figure alone implies. The three frosts already in the table are
  multiplied like colours, which is the best available and may be understating
  the effect at the centre of a beam. ⚠ Worth knowing before a plot promises a
  level through a heavy frost.

  **⭐ AND IT IS MEASURABLE, in about fifteen minutes, with a meter.** No
  manufacturer publishes this because it depends on the beam the diffusion is
  sitting in, so a real reading beats any amount of reading around it:

  1. Point a Source Four at a wall and note the **centre-beam footcandles**.
  2. Drop an **R119** in the frame and read it again.
  3. **If the ratio is about 0.89** — the transmission on file — then absorption
     is the whole story and multiplying is right.
  4. **If it is materially lower**, say 0.75, the scatter is costing more at the
     centre than the number implies, and every level through a frost is
     currently overstated.

  ⚠ **Change nothing on one reading.** Do it at two throws and on two lens
  tubes: if scatter is the cause, the loss should grow with the width of the
  beam, and if it does not then something else is going on. **Jerry has an R119
  to hand** *(2026.09.28)*; what is not confirmed is a light meter.

- **❓ THE SOURCE 4WRD II PHOTOMETRY GUIDE — the one document that would finish
  it.** *(2026.09.28.)* The 4WRD II is a retrofit burner: pull the HPL out of a
  Source Four, put this in, and the fixture is an LED. **Same lens tube, same
  field and beam angles, same symbol** — so it is a LAMP in this codebase, not a
  fixture, and it now sits in `LAMP_WATTS` at 150 W.

  **⚠ What the datasheet does NOT let us do is compute levels**, and the reason
  is worth writing down because the arithmetic looks so available. Page 5 gives
  **lumens per lens** for the 4WRD beside the HPL 575 and 750 — a whole table,
  same document, same measurement. It is tempting to divide one column by the
  other and call it a lamp multiplier.

  **🔴 `LAMP_MF` is a CANDELA multiplier** — ETC's own "Cd MF" columns — and a
  lumen ratio is not that number. An LED source and a filament do not fill a lens
  the same way, and the table proves it: the ratio to HPL 575 runs **1.17 at the
  26° and 1.62 at the 90°**. If it were one property of the lamp it would be one
  number. It is not, so a derived multiplier would be wrong by up to a third at
  the ends, in a figure someone would point a dimmer check at.

  ⭐ **A real fact fell out of it anyway:** the 4WRD does relatively better in
  WIDE lenses than narrow ones. That is source geometry, and it is the kind of
  thing a designer choosing between a retrofit and a new fixture would want to
  know.

  **➡ The datasheet points at a "Source 4WRD II Photometry Guide" at
  etcconnect.com.** That is where the candela lives. Same shape as the
  ColorSource Spot: the guide on file had output modes and the DMX profiles were
  in a different document entirely. **Until it is fetched, an S4 with a 4WRD
  gives a load figure and refuses to give a level** — which is the right answer,
  but only half of one.

- **❓ A LABEL DEFINITION — what goes in which container, editable.** *(Jerry,
  2026.09.28.)* **A popular drafting package lets you define a label legend**: an
  editor where any field can be assigned to almost any position around the
  symbol, saved as a definition and applied to a plot.

  **⭐ Everything about notation is currently a decision in code.** Colour and
  focus in front across the lens, the stack behind, the unit number in the body,
  the hexagon carrying the address when there is no dimmer — each was argued out
  once and then frozen into `symbols.notation`. **They are good defaults and
  they are not universal**: a designer whose house patches differently, or who
  simply wants the wattage shown, has no way to say so.

  ⚠ **This is not "make the notation configurable" as a tidy-up.** Three things
  make it hard, and they are the reason to write the item down rather than start
  it:

  - **A definition has to survive the geometry.** Positions are not slots on a
    page — the stack follows the symbol as it rotates, the colour label steps
    further out when it would touch a neighbour, and containers clear the symbol
    by its own radius. An editor that offers "top left" would be lying.
  - **The shapes carry meaning.** RP-2 §6.14.1 puts the sense in the container,
    not the position, so letting a user draw a circuit in a circle would produce
    a plot that reads wrong to anyone who knows the standard. Whatever the editor
    allows, **the key has to explain what the plot actually did** — which is
    already true for the address in the hexagon.
  - **Screen and paper both have to obey it.** `symbols.notation` draws the
    paper and `render.ts` draws the screen, and they already differ on purpose:
    the screen draws only the channel. A definition would have to say what it
    means for a view that deliberately shows less.

  **➡ The cheap first step is not an editor.** It is naming the current
  arrangement as *a* definition — the default one — so there is something for a
  second one to differ from. Until that exists, "configurable" has no shape.

- **❓ SPEAKER PLACEMENT.** *(2026.09.28.)* A tester asked whether the plot
  should carry audio and video as well as light — her shows are not
  fixture-heavy and everything shares the same air. **Jerry has a sound designer
  he works with, and they had already discussed adding speaker positions**, so
  this is a considered direction rather than a request from outside.

  **⭐ What makes it tractable is what it does NOT have to do.** A speaker has a
  position, a trim, an aim and a footprint on the drawing. It does not need
  photometrics, and **nothing here should attempt coverage prediction** — that is
  a different discipline with its own physics, and the rule this project lives by
  is that every figure names the document it came from. There is no datasheet
  that makes a guessed dispersion pattern true.

  ⚠ **So the line is: positions and clearance, not coverage.** Draw where it
  hangs and what it occupies. Say nothing about what it sounds like.

  **➡ And it is the same job as the clearance item already on this list.** The
  app does not know about masking, scenery or rigging points, so it accepts a
  trim that hangs a unit into a border. **Adding "what else is in the air" is one
  piece of work whether the obstruction is a leg, a projector or a line array** —
  which is an argument for building the general thing once rather than a speaker
  feature on its own.

  **❓ Still open:** whether a speaker is an instrument with a different symbol
  or a different kind of object entirely. The schedule, the hookup and the patch
  are all lighting paperwork, and a speaker that appears in a channel hookup
  would be wrong.

- **❓ Adding a fixture type — open discussion in `docs/FIXTURE-TYPES.md`.**
  Address shapes instead of bare channel counts, whether a type could arrive as
  a package rather than as code, and a four-rung ladder for making it easier.
  **Nothing decided.** Opened 2026.09.28.

- **⚠ Before printing a `_source` string anywhere, read it first.**
  The photometric tables carry a `_source` beside every figure, and it is
  documentation that happens to live in a dict — **nothing in the codebase reads
  it.** So it has never been checked for what a stranger should see. At least one
  cites a real production by name (`FAMILY_WATTS["SHEHDS"]`), and others quote
  datasheet page numbers verbatim.

  Printing provenance on the paperwork is a good idea and very much this
  project's habit — *every figure names its source*. **The day it is built, these
  strings stop being notes to ourselves and become published text**, and they
  should be read through once with that in mind rather than discovered on a plot
  in a theatre.

- ~~Fixture names from paperwork do not match the photometric table keys.~~
  ✅ **Done 2026.09.23 — `server/plotedit/fixture_names.py`.** Measured against
  the real archive first: **none of the 38 distinct names matched**, so an
  imported plot drew correctly and was silently unlit. Now **81% resolve**
  (196 of 242 instruments) and the rest carry a stated reason.

  Three layers: **normalise** (strip the maker, unify Source4/S4, deg/°, repair
  latin-1 mojibake), **ALIASES** for what normalising cannot reach, and
  **NO_DATA** for real fixtures with no figures on file. Photometrics, the symbol
  picker and `POST /resolve-names` all go through it, and the footcandle note
  says how a name was read: *"at HPL 575 (MF 0.78) ['ETC Source4 26deg' read as
  'S4 36']"*.

  **ColorSource datasheets fetched 2026.09.23** — the Spot photometry guide (13
  pp, all nine lenses plus the zooms, three output modes) and the CYC datasheet.
  **The archive is now at 91%**, 221 of 242 instruments.

  **The archive is at 98%** — 237 of 242 instruments. The last ambiguous name,
  `ETC Source4 LED 26deg`, was settled by asking: Jerry confirmed the eight on
  *Wizard of Oz* (2022) were **Lustrs**. The paperwork itself had already
  narrowed it — they load at 140w against 166w for the ColorSource units in the
  same rig, so they were a different fixture — but only he could say which array.

  **All that remains is a hazer and a strobe, which are not luminaires.** That is
  the correct floor, not a gap.

- ~~Ask Altman for the Spectra Cyc IES file.~~ ✅ **Jerry found them on Altman's
  support page, 2026.09.23.** No email needed — Altman publish IES for the
  Spectra Cyc **100 and 200** (not the 50). `ies.py` parses LM-63, and the
  Spectra Cyc 100 is now the one fixture in the table whose figures come from a
  **real 46 × 73 goniometric measurement** rather than a datasheet table:
  4,612 cd, 4,727 lm, 94.1 W, peak at 70° off nadir. The datasheet corroborates
  the lumens exactly.

- **🔴 Were the Wizard of Oz cycs 50s or 100s?** The paperwork says
  `Altman Spectra CYC 50` at 50w — but in Lightwright the load comes from the
  library entry for the named fixture, so the name and the wattage are ONE fact,
  not two. **Jerry believes they were 100s.** Both models are in the table; the
  alias still points the paperwork name at the 50, which has no photometrics.
  **Settle it and the alias changes, and four instruments gain real numbers.**

- **More IES files are worth having.** Altman publish them for several fixtures;
  ETC publish IES for the whole Source Four and ColorSource range. Anywhere a
  datasheet is thin, the IES is not.

- ✅ **Symbols approved 2026.09.23.** Jerry passed all 18 of Rev 3 plus the three line weights. **The gate on drawing more is open.** Next: §6.6 cyc units and §6.7 striplights — both are in his archive (Altman Sky Cyc, ColorSource CYC, Altman Spectra Cyc). Then followspots §6.10 and accessories §6.13.

  **Still not settled by approval:** the PARNel axis line means either beam axis or lens rotation, and both look identical, so his eye cannot resolve it.

---

**⚠ Resist the urge to start at step 4.** Steps 1–3 are where the coordinate
system and the data model get settled, and they are cheap to change until
something is drawn on top of them.

---

## Positions — started 2026.09.23

**Jerry: "we should do positions next — for now, horizontal ones — catwalks,
electrics, etc," and then: "catwalks are also FOH (front of house) positions."**

Done:

- **`type` on a position** — `electric` · `pipe` · `grid` · `catwalk` · `truss`.
  It decides the drawing, and the distinction is physical. An electric is one
  heavy batten line. **A catwalk is a WALKWAY**: two architectural edges with a
  hanging pipe inboard of the downstage one, because a person stands on it and
  the units hang off the rail rather than down the middle. A unit drawn on the
  centre of a catwalk is drawn three feet from where it is.
- **FOH.** A catwalk is front of house, over the audience, downstage of the
  plaster line — **negative y**. `foh_extent()` reports how far downstage the
  positions reach and `plot_to_pdf` shifts the origin to cover it. Without that
  the catwalk is clipped off the bottom and only the clipping guard would say so.
- `railOffset` overrides the pipe's inboard distance — **it varies by house, so
  take it off the venue's section rather than from the default.**

### ✅ Which end is unit 1 — answered 2026.09.23

**Jerry: *"SR is unit 1 because the numbers actually go house left to house
right — easier to read, and visualize from the house."*** And: *"on a pipe that
runs US -> DS, I tend to have unit 1 be farthest DS."*

**⭐ The principle is the reading direction from the house, not the geometry.**
Unit numbers run the way a person reads the plot while standing in the room:
left to right across a lateral position, near to far on one running up and down
the stage. It is a rule about legibility, and the coordinates are only how it
gets expressed.

| Position runs | Unit 1 at | In this file's coordinates |
|---|---|---|
| Stage left–right | stage right (= house left) | the maximum x, counting down |
| Upstage–downstage | farthest downstage | the minimum y, counting up |

The two move opposite ways along their axes. **That looks like an inconsistency
and is not one** — they are the same rule seen from the house. ⚠ So if this is
ever unified, unify it on the **reading direction**, never on the sign of a
coordinate.

*(Corrected 2026.09.23: an earlier version of this note led with the coordinate
mechanics and called the two rules opposites, which is true and is not the
point. Jerry: "I don't really care about x and y, it's not used except for maybe
hanging." The reason is what generalises to the cases nobody has coded yet.)*

`positions.py` has `axis()`, `number_from()`, `order()`, `number()` and
`describe()`, which states the convention in words for the plot's own notes —
*"Elect 1: unit 1 at stage right — numbers read house left to house right."*
**`numberFrom`** (`SR`/`SL`/`DS`/`US`) is the override, and always wins.

Two refusals: **two units at one coordinate warn** rather than being ordered
arbitrarily, and **nothing renumbers automatically**, because on a hung plot a
renumber is a different document from the one taped to the pipe.

### ✅ Circuits — 2026.09.23

**Jerry: *"circuits depend on the house — no set order."*** That one sentence is
the whole design. **`circuits.py` never invents a circuit number.** Unit numbers
follow a rule and can be generated; circuits do not and cannot. A house wired its
pipes in whatever order made sense to whoever did it, and the only source of
truth is that house — its rep plot, its circuit map, or its ME standing under the
pipe.

So the module **records what the house says and checks the plot against it**:

- `circuits` on a position is an **inventory** in the house's own order. Bare
  numbers (`[7, 8, 9]`) or records with a location along the pipe.
- `circuitSource` — **a circuit list without a provenance is a rumour**, and an
  unsourced list is reported as one. This is what `/venue` asks for the rep plot
  to fill.
- `check()` catches a circuit the house has not got, a position not in the plot,
  and a position with nothing recorded (not an error — but no load table can be
  built for it).
- **A twofer is reported, never rejected.** Two units on one circuit is legal and
  common; it is a LOAD question, and it goes to Art.
- `match_to_units()` **refuses when the house gave no locations.** Pairing a
  circuit list against units in order would look like a result and be a guess,
  and a plot patched to the wrong circuits reads as correct until half the rig
  does not come on.
- ⚠ And when it *can* match, it **reports every doubling it creates** — there are
  routinely more units on a pipe than circuits under it. A matcher that silently
  doubles up is worse than one that refuses: the refusal gets dealt with, the
  silent twofer gets discovered by a breaker.

The circuit is drawn in a **hexagon** (§6.14.1 — the shape carries the meaning)
and has a column on both the instrument schedule and the hookup.

### ✅ Dimmer per circuit — 2026.09.23

**Jerry: *"most houses have circuit per dimmer. We need to account for that."***

RP-2 §6.14.1 gives **three control models and notates them differently**, so this
changes the drawing, not only the data:

| `control` | Containers | |
|---|---|---|
| **`dimmer-per-circuit`** *(default)* | hexagon + circle | The circuit is hard-wired to its own dimmer. **One number, not two** — RP-2 labels the hexagon "Circuit & Dimmer" |
| `hard-and-soft-patch` | hexagon + rectangle + circle | All three differ, so all three are drawn |
| `no-soft-patch` | hexagon + circle | The console addresses dimmers directly |

**Drawing two containers in a dimmer-per-circuit house is not harmlessly
redundant — it tells the electrician there is a patch to make, and there is
not.** A dimmer that merely repeats the circuit is dropped, and a plot that gives
them *different* numbers is reported: either the control model is wrong or one of
them is a typo.

**And the load follows.** With no patch to hide behind, **the load on a circuit
IS the load on a dimmer.** `circuits.load()` totals watts per circuit and, given
the house's per-dimmer rating, reports headroom. The 2026.09 fault was a pack
over capacity, and this is the arithmetic that would have shown it.

- **The rating is never assumed.** 2400W is the common 20-amp figure and it is
  also wrong in plenty of buildings. Without it, loads are reported and nothing
  is judged — a capacity check against an unconfirmed number reads as a *pass*.
- **A tungsten unit's watts belong to its LAMP**, not its body: the same Source
  Four is 575W or 750W depending on what is in it. `lamp_watts()` reads it off
  the lamp name, which is exact rather than inferred.
- ⚠ **And it refuses to read a number out of just any string.** "Regulated 3200K"
  is an LED output mode; a loose search finds 3200 in it and calls it 3200 watts
  — a number that looks real, lands in a load total and trips a breaker. A lamp
  name has to look like one.

**✅ Wattages pulled off the ETC datasheets, 2026.09.23.**

`FAMILY_WATTS` keys them by **engine, not lens tube**, which is how ETC publish
them — one entry instead of the same number repeated across 47 rows.

| | W | Source |
|---|---|---|
| Series 2 Lustr | 167 | S4 LED Series 2 datasheet p2, "typical" |
| Series 2 Tungsten HD | 208 | same |
| Series 2 Daylight HD | 248 | same |
| ColorSource Spot | **160 / 141 / 115** | Photometry Guide — **by MODE** |
| ColorSource CYC | 133 | CYC datasheet p2 |

**⚠ An LED's draw depends on its output mode**, and that is the thing a single
number per fixture gets wrong: a ColorSource Spot is **160W at Maximum Output and
115W regulated to 3200K**. 28% — the difference between four and five units on a
20-amp dimmer. `watts_for(kind, lamp, mode)` is the one place that knows both
rules, and ETC's figures are **typical, not peak**, which it says out loud.

**⭐ And an S4 with no lamp recorded is now an HPL 575** — Jerry: *"ETC S4
incandescents are 575 watts unless noted; there are 750."*

**This changes every computed level on a plot that does not state its lamp.** ETC
*measured* the candela at HPL 750, and `ref_lamp` still says so — but a 750 is
not what is in the fixture. Computing at the reference overstated output by about
a quarter, **in the direction that looks safe**: the plot promised light the rig
would not deliver.

**Corroborated from outside the code.** `how-we-light.md`, built from Jerry's own
paperwork before any of this existed, puts a 575 S4 26° at 14 feet through
R52+R119 at **163 fc**. The tool now returns 163.

### ✅ 90-degree mounts, and label clearance — 2026.09.23

**Jerry: *"most plots display the instruments on even 90 degree mounts. Even
though the lamp may be actually pointing 320 degrees, it would be displayed on
the plot as 0 degrees. Usually it's an option."*** He was unsure whether the
standard covers it. **It does, in so many words** — RP-2 p.2: *"It is acceptable
to visually orient the angle of each drawn luminaire to either focus points or
90° axes."*

`symbolAngle` — **`orthogonal` by default**, `focus` for the true angle.

**🔴 The snap is COSMETIC and the tests hold it that way.** A unit *drawn* at 0°
while aiming at 320° is a drawing convention; a unit *computed* at 0° would be a
lie about where the light lands. `test_agreement.py` renders the same plot in
both modes and requires every throw, pan and footcandle to be identical —
verified to fail when a difference is introduced on purpose.

**Labels.** The notation now clears each symbol **by the symbol's own radius**
rather than by a fixed 11 inches, which had been putting the channel circle on
top of every ellipsoidal — an ERS reaches past a foot from its yoke, and further
with a barn door on the nose. And boom labels come off the plan view, which is
both what Jerry asked for and what RP-2's own §6.12 plate does: the plan symbols
carry no numbers, the layout beside the plot carries them all. What stays in plan
is a short name, placed outboard, so a reader can tell which boom the point is.

### ✅ Testing the tests — 2026.09.23

**Twice in one day a suite printed its pass/fail verdict in the MIDDLE of the
file**, so anything appended afterwards ran without affecting the exit code: the
suite could print failures and still exit 0. `test_package.py` and
`test_agreement.py`, both found by accident, both while adding checks that landed
in the dead zone.

**`verify_suites.py` makes it a thing that gets checked rather than noticed.** It
injects a guaranteed failure into each suite, runs it, restores the file, and
requires **exit 1 AND the failure named in the output**.

    cd server && python3 verify_suites.py

All six pass. **Run it whenever a suite gains a section.**

⚠ Worth recording: the first two attempts to prove a break were themselves
broken. One mutated a line the assertion never looked at, so nothing could fail.
The other inserted an unindented statement into an indented block, so the run
died of `IndentationError` and "exited 1" for the wrong reason — which looks
exactly like success. The script now injects at **top level only** and reports a
syntax error as *unverified*, never as a pass.

**A test you have never watched fail is not yet a test.**

### Still to do

- Auto-numbering along a position, once the direction is known.
### ✅ Booms and box booms — 2026.09.23

**⭐ In plan a boom is a POINT.** Every unit on it shares one x and one y and is
told apart only by its **height** — which is why a boom needs its own everything.
`height` is not a nicety on a vertical position; it *is* the position, and a unit
without one cannot be drawn, numbered or hung. `check_booms()` says so by name.

RP-2 §6.12, followed:

- **Hatched in plan.** *"Hatch or shade acceptable for top view of boom."* Four
  units at one point would otherwise be a heavier blob; the hatch says *this is a
  stack*.
- **The readable layout goes BESIDE the plot** — the pipe as an elevation with
  each unit at its height. `boom_elevation()`.
- **⚠ And it is NOT TO SCALE, which it prints on itself.** RP-2 permits this
  (*"layouts may not be to scale"*), but every other line on this sheet measures
  true and carries a scale bar to prove it. A schematic that did not announce
  itself would be read with a rule. **The heights are the data; the spacing is
  not.**
- **One layout per plot**, per the standard. `boomLayout`, and two on one drawing
  is reported.
- **Three mounts**, because they are different hardware: **floor plate** (needs
  floor space and a sandbag), **boom base**, **flange** (already in the
  building). A missing mount is flagged.
- **Numbered top down** — the reading direction for anything standing up, and
  what RP-2's own plate shows: unit 1 at 8'-0", unit 4 at 2'-0".

**A box boom is a boom that is front of house**, so it carries `foh` and lands at
negative y with the catwalks.

**🔴 A plot with booms needs a bigger sheet.** The elevations sit off the
stage-left edge, and the sample no longer fits Tabloid at ¼" — the export
**refuses** rather than clipping, and names ⅛" as what would fit. Arch D at ¼"
holds it, which is the sheet Jerry draws on anyway.

### ✅ 90-degree mounts, and label clearance — 2026.09.23

**Jerry: *"most plots display the instruments on even 90 degree mounts. Even
though the lamp may be actually pointing 320 degrees, it would be displayed on
the plot as 0 degrees. Usually it's an option."*** He was unsure whether the
standard covers it. **It does, in so many words** — RP-2 p.2: *"It is acceptable
to visually orient the angle of each drawn luminaire to either focus points or
90° axes."*

`symbolAngle` — **`orthogonal` by default**, `focus` for the true angle.

**🔴 The snap is COSMETIC and the tests hold it that way.** A unit *drawn* at 0°
while aiming at 320° is a drawing convention; a unit *computed* at 0° would be a
lie about where the light lands. `test_agreement.py` renders the same plot in
both modes and requires every throw, pan and footcandle to be identical —
verified to fail when a difference is introduced on purpose.

**Labels.** The notation now clears each symbol **by the symbol's own radius**
rather than by a fixed 11 inches, which had been putting the channel circle on
top of every ellipsoidal — an ERS reaches past a foot from its yoke, and further
with a barn door on the nose. And boom labels come off the plan view, which is
both what Jerry asked for and what RP-2's own §6.12 plate does: the plan symbols
carry no numbers, the layout beside the plot carries them all. What stays in plan
is a short name, placed outboard, so a reader can tell which boom the point is.

### ✅ Testing the tests — 2026.09.23

**Twice in one day a suite printed its pass/fail verdict in the MIDDLE of the
file**, so anything appended afterwards ran without affecting the exit code: the
suite could print failures and still exit 0. `test_package.py` and
`test_agreement.py`, both found by accident, both while adding checks that landed
in the dead zone.

**`verify_suites.py` makes it a thing that gets checked rather than noticed.** It
injects a guaranteed failure into each suite, runs it, restores the file, and
requires **exit 1 AND the failure named in the output**.

    cd server && python3 verify_suites.py

All six pass. **Run it whenever a suite gains a section.**

⚠ Worth recording: the first two attempts to prove a break were themselves
broken. One mutated a line the assertion never looked at, so nothing could fail.
The other inserted an unindented statement into an indented block, so the run
died of `IndentationError` and "exited 1" for the wrong reason — which looks
exactly like success. The script now injects at **top level only** and reports a
syntax error as *unverified*, never as a pass.

**A test you have never watched fail is not yet a test.**

### Still to do

---

## Closed, not forgotten: the SHEHDS units

**Jerry, 2026.09.23: *"forget the SHEHDS units, that was a one off."*** Their
**candela is unpublished and is not being sought** — no meter, no email, no
standing task. They go on specials and isolated areas where a computed level was
never the point.

**What was worth keeping before closing it: they are 350W each**, from the model
name and corroborated by his own *Without Consent* rig notes, which planned a
separate circuit around them. So they now count properly in a load table — the
one place their absence would have silently understated a total.

**➡ "Forget it" is worth reading twice.** The output was the part to drop. The
wattage was sitting in a business file the whole time and was the part that
mattered for safety.

---

## Ladders and tormentors — 2026.09.23

Reading §2.3 properly for these turned up rules that apply to everything, and one
place where **Jerry's practice and the standard are opposite.**

**A ladder hangs; a tormentor is bolted on.** Neither takes a floor mount. A
ladder needs a **trim** instead (§3: *"trim height for all hanging positions that
can change height"*), and asking it for a boom base is asking for hardware that
does not exist. A tormentor is asked for nothing at all.

**⭐ §2.3.2 supplies the tiebreak a ladder needs:** *"on onstage booms or other
vertical hanging positions... from top to bottom, **downstage to upstage**."*
Units hang on both sides of a ladder frame at the same height, which without that
second clause is an arbitrary order — the exact thing that had been flagged as
*"legal on a sidearm, but say which side."* The standard already said which.

**§2.3.2's FOH rules, now implemented:** a position parallel to centerline numbers
from **nearest the plaster line**; a **box boom** numbers from **the units
closest to centerline**.

**⚠ And "box boom" turned out to mean two different things.** A plain vertical
pipe in a box is a point, numbered top down. A rail with real horizontal extent
is numbered from centerline. `is_vertical()` was trusting the type NAME and got
the second one wrong — it measures the extent now. The plot would have looked
entirely right.

### ✅ No divergence after all — corrected 2026.09.23

I had recorded a conflict between Jerry's numbering and RP-2 §2.3.2. **There is
not one.** Jerry: *"oops, I was thinking how I do channels — the spec is right."*

**Unit numbers follow the standard: stage LEFT to stage right across a batten.**
The default is `SL`, and the divergence table is deleted.

**Channels are a different field, and RP-2 does not cover them.** The standard
requires a channel to be *shown* on the plot and says outright that channel
hookups are *"not addressed in this document."* So Jerry's convention — **house
left to house right, channel 1 at stage right** — conflicts with nothing.
`channel_order()` and `channel_note()` record it as a house convention rather
than a departure.

**⚠ Unit numbers and channels therefore run in OPPOSITE directions across the
same batten, and that is correct.** A unit number is read by someone standing
under the pipe with a wrench; a channel by someone sitting in the house reading
the plot. Different readers, and they are allowed to run different ways.

**➡ The lesson is about the question, not the answer.** *"Unit 1 is stage right"*
was a true statement about the wrong field, and a whole apparatus got built on
it — a divergence table, a legend line, advice about plots going to unfamiliar
houses. **When a stated convention contradicts a published standard, the first
move is to ask which field it applies to, not to record a conflict.**

---

## The section — 2026.09.23

**`plot_to_section.py`**, built to RP-2 §3's own checklist rather than to what
looked reasonable. The old `section()` in `scaled_pdf.py` had **no callers at
all** — written, never wired up, never checked against the standard.

**⭐ A section answers two questions the plan cannot: how low can this pipe go,
and does the light reach the actor's face.** Which is why §3 asks for two things
the old one had neither of:

> *"Scaled representation of the luminaire that determines batten height mounted
> in each position."* · *"Human figure (or 'head height') in scale."*

A unit drawn as a dot cannot show whether it clears the masking. A head-height
*line* cannot show whether a 30° front light hits a face or a forehead.

**⚠ And it is ONE luminaire per position, not every unit** — §3 says the one that
*determines* batten height. Drawing all sixty turns the section into a smear and
hides the only thing it is for. The default is the unit nearest the cut;
`governing` on a unit overrides it, because which unit constrains a trim is a
judgment the designer makes rather than arithmetic.

**Also to the checklist:** where the cut is taken, the stage floor named as
**vertical zero**, the plaster line as **horizontal zero**, DS edge and US limit,
booms and ladders in **side elevation** (the one view where a boom is not a
point), trim on every position, and a vertical sightline from a stated audience
eye point.

**What it refuses to fake:** with no `sightPoint` recorded it draws no sightline
and says to ask the venue for the worst seat; with no masking or scenery it says
in orange that **obstructions are NOT proven clear**. A section that silently
omits the masking is the one that gets a pipe hung into a border.

**🔴 The bug worth remembering.** The first version derived each symbol's
rotation from its *elevation angle* — but elevation is **unsigned**. 40° describes
both "down and upstage" and "down and downstage", so half the rig was drawn
aiming backwards while every number on the sheet stayed correct. It now comes
from the real direction vector, and the tests check the nose direction in all
three cases.

---

## The instrument key — 2026.09.23

**`key.py` + `plot_to_key.py`**, to RP-2 §5.1's list. §5.0: *"Placement is
acceptable in any location that does not conflict with other information"* — so
it renders on its own sheet, and `key.draw()` is the same function, ready to drop
onto the plot once there is room.

**⭐ A key is not a parts list. It is the drawing's own dictionary** — it says
what each shape means so a stranger can read the plot without asking the
designer. That is why §5.1 asks for the SYMBOLS and not just names, and why they
are drawn at the plot's own scale: a key drawn at a different size teaches a
shape the reader will never see again.

To the list: every luminaire with its count and description · **field and beam
angles** · wattage · every notation explained, and the explanation changes with
the house's control model · colours with transmission · **colour manufacturer
designations, but only the ones actually used** (a key explaining L = Lee on a
plot with no Lee wastes the reader's attention) · accessories with their symbols.

**⚠ It reports what is ON THE PLOT, never the fixture table.** A key listing
instruments nobody hung is a key nobody finishes reading. And a type the tool
cannot identify is **flagged in the key** rather than quietly given no angle —
the key is what someone reads instead of asking.

**On beam spread:** §5.1 says give it "if the numeric value is not part of the
luminaire's name". It is given always, because `S4 26` names the **nominal**
barrel while the measured field is 25° and the beam 18°. The name is the product;
these are the light.

**The layout bug worth remembering:** the first version spaced rows by a constant
and drew the symbols nose-up, so a 1'-8" ellipsoidal overlapped the row above it.
Rows are spaced by each symbol's own radius now. **A key whose symbols collide
teaches the wrong shape, which is worse than no key.**

---

## The room is the whole room — corrected 2026.09.24

**Jerry: "the FOH catwalk would need to be inside the room. It looks like the
catwalk is outside the room?"** Then: **"it's a black box so there's technically
no plaster line."** Both were right, and between them they took out a model I had
built three features on top of.

**What was wrong.** I had treated `room` as the STAGE, with the house beyond it
at negative y. So a catwalk went to y = -11, outside the drawn rectangle — and to
reach it I added `foh_extent()`, an origin shift in `plot_to_pdf`, `fohExtent()`
in the browser and a canvas extension in `fitView()`. **Four pieces of machinery
to reach outside a room that already had space inside it.** The test room is 33' x
38'; the audience sits in it.

**What is right.** The room is one rectangle holding house and stage. All four
pieces are deleted or retired. Front of house is now a matter of WHERE a position
sits — and in a black box, of what the designer SAYS, because there is no
proscenium for geometry to read. The seating decides it, and at the test room the
risers move.

**RP-2 already knew.** §3 asks for *"proscenium, plaster line, smoke pocket, or
the 'horizontal zero' location"* — a plaster line is one KIND of datum, not the
only one. `horizontal_zero()` returns whichever is declared and its NAME, and the
section prints that name rather than stamping "PLASTER LINE" on a room that has
none. The test room declares **the centre of the room**, Jerry's choice: findable in
an empty room, where a downstage wall is arbitrary when the audience can end up
on any side.

**⚠ A datum is not the storage origin.** Coordinates stay corner-based, so no
plot on disk has to be rewritten to say the same thing differently. What the
datum changes is where dimensions are measured FROM.

### 🔜 Deferred, at Jerry's word

**Changing the origin so the datum drives the drawing's coordinates** — "we can
later add a feature to change the origin so that the plaster line can define
things, but for now we can leave it."

### Two guards that were lying

**The clipping guard reported a SIZE problem for a POSITION problem.** The section
spanned 53' on a sheet holding 70' and was clipped all the same — one sight point
lay ten feet off the left edge. It now names **which edge and by how much**, so
the reader is not sent to change the scale when a stray coordinate was the fault.

**And the PDF export refused on ANY warning.** A grazing pool is a true note
*about* the plot, not a reason to withhold the plot — refusing over it would mean
a rig with one flat side light could never be exported. Only CLIPPED is fatal
now; the rest come back in an `X-Plot-Notes` header.

---

## Metric — what is left, from the 2026.09.25 survey

`plotedit/units.py` and `test_units.py` are in on the `metric` branch. Nothing is
wired up: they are the foundation and the guard rails.

**⭐ Two findings that make this smaller than it looks.**

**The physics is already metric and needs no new data.** Illuminance is candela ÷
distance², so the same published candela gives FOOTCANDLES with the distance in
feet and LUX with it in metres. An S4 26 at 13'-4" reading 773 fc is the same
measurement as 4.06 m reading 8321 lx. Same table, same gel percentages, same
angles.

**And the two scale systems meet exactly.** 1/4" = 1'-0" **is 1:48** — a foot is
twelve inches and a quarter inch goes into twelve exactly forty-eight times. So
both reduce to points-per-foot and `scaled_pdf` can keep one number:
`points_per_foot("1/4")` returns 18.0, which is precisely what it already
computes as `0.25 * 72`. **The generalisation is drop-in**, and `test_units.py`
pins that for every existing scale.

**The four remaining pieces, in the order to do them:**

1. **Thread the setting through the display layer.** `plot.units`, then make
   `fmt_ft` (33 call sites), `fmtFt` (15) and `parseFeet` unit-aware. Mechanical
   and shallow. ⚠ **Feet stay the stored unit** — every saved plot, every test
   fixture and all the RP-2 symbol geometry are in feet, and a Source Four is 22
   inches long in Birmingham too. Convert at the edges, which is what the DXF
   importer already does.
2. **Lux.** A ×10.7639 at the display edge. 🔴 **The label is the risk**, not the
   arithmetic: `footcandles` appears in the API response, the schedule column and
   the inspector, and "179 fc" printed over a lux number is a false statement
   that looks authoritative.
3. **The drawing scale.** The only part that is not a conversion. `scaled_pdf` is
   built on `paper_in_per_ft` and its own comment calls that "the whole trick".
   Generalise to points-per-foot, add a metric list to the fit-to-sheet chooser,
   and a scale bar that reads 0–10 m. **Give this its own pass** — it is where
   the risk is.
4. **✅ Paper — done 2026.09.30.** A4, A3, A2, A1 and A0 are all offered on a metric plot.

**🔴 The one judgement call, and it is Jerry's: defaults must be IDIOMATIC, not
converted.** Head height is 5'-6" imperial; a metric designer says **1.7 m**, not
1.676 m. Converted defaults produce numbers no European would type, and they then
travel into drawings as evidence of a measurement nobody took. The current list
is head 1.7, face 1.6, seated 1.1, deck — it wants reviewing before it is used.

**⚠ And the danger throughout is DOUBLE CONVERSION**, which is silent: a length
converted twice is out by 10.76 and still describes a plausible room. The
round-trip tests exist for that, including one asserting that converting twice is
**not** the identity.

**What stays imperial regardless:** RP-2 is a US standard, so symbol geometry
does not change. Lamp names (HPL 575) and gel numbers are product codes.

---

# Patch completeness, and what the plot does not tell you

*(Jerry, 2026.09.26, after an evening lost to an Eos file that was simply empty.)*

**1. Warn on a channel that talks to nothing.** An instrument with a channel but
**neither an address nor a dimmer** is not yet a working unit, and nothing in the
editor says so. The export refuses now when *every* unit is like that, which is
the loud case. The quiet case is worse: a plot where seventeen of twenty-four are
unaddressed exports happily, and the seven that made it are the only ones that
light. That warning belongs in front of the designer while they are drawing, not
at the moment they export.

⚠ **An address and a dimmer are alternatives, not a pair.** A conventional unit
in a dimmer-per-circuit house has a dimmer and no DMX address of its own; an LED
unit has an address and no dimmer. Either is a complete answer.

### 🔴 REVISED 2026.09.28 — warn on the CHANNEL, not on the patch

**Jerry: the LD may not know the address the electrician wants to put the
instrument into.** So the warning above, as written, is wrong, and it was never
built — which is lucky.

**A channel number is the designer's.** It is how the board is laid out, it is
theirs to decide, and a mounted instrument without one is an omission only they
can fix. **⭐ That is worth warning about while drawing.**

**An address is the electrician's.** On most jobs the designer hands over a plot
and the ME decides what goes where in the patch — so a plot full of blank
addresses is not an unfinished plot, it is **the normal state of a finished
design.** A warning there would fire on every honest drawing and be trained away
within a day, which is worse than no warning: it teaches people to ignore the
place warnings appear.

**✅ What stays.** The export refusal, which fires when a patch file would be
empty. That is not a drawing-time nag — it is the moment a file is about to go
to a console, where the address genuinely has to exist by then.

**➡ So the item is: warn on a mounted instrument with no channel number.** There
is no such warning today; the memory of one is this roadmap entry, not code.

Open question: where does it go? Candidates are the instrument inspector, a count
in the status line, and the schedule. Probably all three eventually, but the
schedule is where an ME would look.

**2. Instrument types in the patch.** *Deferred deliberately — keep it simple
for now.* The patch exports `channel<address` and nothing else, so every unit
arrives at the console as a bare dimmer. For a Source Four that is correct: it
**is** a dimmer as far as the board is concerned. For an LED unit it is wrong —
it needs a personality and a block of addresses, and patching it as one address
with an intensity gives a channel that moves the first parameter and nothing
else. On a real rig that reads as a broken light rather than a wrong patch,
which is an hour of somebody's evening to find.

**⭐ Updated 2026.09.26, and the reason it got easier:** the plot now records the
specific model and the DMX personality per unit, and `dmx.py` turns those into a
channel count with a datasheet behind it. The schedule shows `2/1-2/15`. So the
export no longer needs new facts — it needs to carry facts the plot already has.

**⚠ And the gap is now visible rather than merely present.** The schedule tells
the truth about the rig and the file handed to the console does not: two Lustrs
on different personalities export identically, as bare dimmers at one address
each. That is a worse state to leave alone than before, because anyone reading
both will believe the export.

What is still unknown is the Eos end — what a patch entry with a fixture type
looks like in USITT ASCII, and whether it can carry a personality at all. The
format has never been verified against a console (see the header of
`exports.py`), so this waits on a real Eos export to diff against, not on more
reasoning from the spec. Jerry, 2026.09.26: "we will have to find out how to
export it, but that's another day."

⚠ Eos asks on import whether to bring fixtures in as **Library** or **Custom**;
ETC's manual recommends Custom. That prompt is asking how to resolve fixture
records the file does not currently contain.

---

## How a multi-leg position should number — PARTLY ANSWERED, 2026.09.30

A V or an L is one position made of two straight segments sharing one name, and
the app now lets you make one on purpose. **Renumbering it produces an order
nobody could hang.**

Measured, not inferred — a `>` shaped cove, four units on each leg, no two at the
same coordinate:

```
leg A   x = 0, 4, 8, 12    →  units 1, 3, 5, 7
leg B   x = 14, 10, 6, 2   →  units 8, 6, 4, 2
```

Odds down one leg and evens back up the other, **with no warning**. The cause is
in `positions.order`: one sort key is worked out from ONE leg's geometry — stage
left to stage right, per RP-2 §2.3.2 — and applied to every unit on the name.
When the legs cover the same ground along that axis, they interleave. The
existing guard in `positions.number` misses it because it only fires when two
units share a coordinate *exactly*, which happens at the apex and nowhere else.

A V that runs one way across both legs numbers correctly (verified: 1..10), so
this is not always wrong — which is why the browser now states the risk in the
renumber dialog above the moves and lets the designer judge, rather than
refusing.

### 🔴 The rule not to break while fixing it

Jerry, 2026.09.30: *"you can't just renumber the units"* and *"you can allow the
user to do it, but doing automatically is bad."*

A unit number is not a label the file owns. It is spiked on the pipe, written in
the hookup the electrician is holding, and called out in the dark. Renumbering
rewrites every one of them in the file and none of them in the room. So the fix
here is **a better order when the designer asks for one**, never a tidy-up that
runs by itself. Nothing calls `number()` automatically today and nothing should
start.

### The question

Should a shared name number **along the run** — walk leg 1 end to end, then leg 2
— instead of sorting the whole name on one axis? That is how you would number it
walking the pipe with a pencil, and it needs two things the app does not have:

1. **Which leg comes first.** The segments are a list in file order, which is the
   order they were drawn, not the order they hang.
2. **Which end of each leg is the start.** Two legs meeting at an apex means one
   of them runs "backwards" relative to §2.3.2's stage-left rule.

⚠ Both are answerable from the geometry — the legs share an endpoint, so the run
can be walked from whichever free end is furthest stage left. But it is a
convention decision, not a derivation, and RP-2 §2.3.2 does not cover a bent
position. **Jerry's call.**

### ⭐ And there is now a way round it, which may be the whole answer

**number by clicking** (#74) numbers a run in the order the units are clicked.
Jerry, 2026.09.30: *"One cool feature Vectorworks has is the ability to pick a
starting sequence number and then letting the user fix the sequence by selecting
units."*

That does not answer the question above — it **removes the need to**. The order is
whatever order the designer walks the pipe in, so no convention has to be derived
for which leg comes first or which end starts. It works on a V, an L, a curved
cove and a rig somebody else hung.

**What is still open** is only whether `renumber` — the one-press, geometry-sorted
path — should learn to walk a bent run, or whether a shared name should simply
send the reader to click instead. Today it warns: the dialog says the order came
from the first leg and may alternate, and leaves the choice there. ⚠ That warning
is the thing to revisit, not the interleave itself, which is now avoidable.
