# Layers — what they would mean here

**Status: STEP 1 BUILT, 2026-10-01.** The eight layers are in the plot file, six
of them have chips, and the renderer reads them. Steps 2 to 4 — the DXF, the
layered PDF, user layers — are not built. §6 records the order; the section at
the very bottom records what step 1 actually did, including **three places where
building it contradicted this plan**. Written 2026-10-01 for #82,
which asks:

> If reasonable, design a system where different objects can live on layers and
> a layers' visibility can be turned on/off

⚠ **"If reasonable" is doing real work in that sentence**, so this document tries
to answer it rather than assume it. The short version: **the app already has
layers, in two incompatible schemes, and neither is the one #82 describes.**
Deciding which of the three to keep is the actual design problem.

---

## ⭐ Jerry's answers, 2026-10-01 — these settle §7

> so the plot file needs to have the layers, because we would need to display
> them when we bring it into the app. Can we merge the screen and DXF layer
> together, and then store them in the JSON file? Also do PDF files have layers?
> Eventually we would give the user the ability to add layers

| | |
|---|---|
| **Where do layers live?** | **In the plot file.** A layer the file does not carry is a layer that is gone when the plot is reopened. |
| **One scheme or two?** | **One.** The screen's four and the DXF's six merge into a single set. |
| **Do PDFs have layers?** | **Yes — and the route is proven below.** |
| **User-defined layers?** | **Eventually.** So the design has to allow them from the start, even if the first version ships only the built-in set. |

⚠ **That changes §2's conclusion rather than deleting it.** The observation
stands — the groupings a designer asks for are mostly about instruments — but it
is now an argument about *which layers to offer*, not about whether to have them.

---

## ✅ PDFs do have layers, and this toolchain can write them

PDF calls them **optional content groups**. A reader shows them as a Layers panel
with a checkbox each, and switching one off removes it from the page and from
printing.

🔴 **But reportlab cannot make them.** It is what draws every plot PDF
(`scaled_pdf.py`), and a search of the installed package for `OCProperties`,
`OptionalContent`, `setOCG` and `OCG` returns **nothing at all**. So this is not
a flag to switch on.

⭐ **PyMuPDF can, and it is already a dependency.** It has `add_ocg`, an `oc`
argument on `show_pdf_page`, and `set_layer_ui_config` to toggle one.

**The route, built and measured rather than assumed:** reportlab draws each layer
to its own one-page PDF, and PyMuPDF overlays them onto a single page, each
tagged with its own group.

```
layers in the file : POSITIONS, UNITS
reader's panel     : two checkboxes, both on
dark pixels, both on   1701
dark pixels, UNITS off 1453      ← 248 pixels of ink actually removed
```

⚠ **One trap found while proving it.** `get_layers()` returns the reader's
*configurations* and came back empty, which looked like failure — the groups are
in `get_ocgs()`. And `set_layer(-1, off=[…])` changed the stored state **without
changing what rendered**; `set_layer_ui_config(n, action=2)` is the one that
actually hides the ink. Both are easy to mistake for "it does not work".

---

## ⭐ The merged set — eight layers covering both schemes

| Layer | What is on it | Screen today | DXF today |
|---|---|---|---|
| **Base plan** | the imported venue drawing | `plan` | `BASE` |
| **Positions** | pipes, booms, their mounts | — | `POSITIONS` |
| **Units** | the instrument symbols | — | `UNITS` |
| **Labels** | unit numbers, channels, position names | `labels` | `TEXT` |
| **Pools** | the light on the floor | `pools` | — |
| **Focus** | leaders and focus points | `focus` | — |
| **Dimensions** | rulers and dimension strings | `rulers` (print only) | `DIMS` |
| **Notes** | the key and the notes block | — | `NOTES` |

**What the merge buys, on each surface:**

- **The screen gains four** it never had — Positions, Units, Dimensions, Notes.
  ⭐ "Hide the units and read the pipes" is a thing designers do and the app
  cannot currently do.
- **The DXF gains two** it never had: Pools and Focus are **not written to the
  DXF at all** today, so a CAD reader cannot switch off what was never there.
- **The PDF gains all eight**, having had none.
- **`rulers` stops being a special case.** It is print-only because the screen
  has no Dimensions layer; once it does, it is just a layer that defaults off.

### How user layers fit later, without a second system

The file carries a `layers` array — name, visible, order — seeded with the eight.
⚠ **The built-ins are assigned by KIND and cannot be deleted**, because nothing
sensible happens to a pipe whose layer was removed. A user layer is assigned by
the designer, and an object carries at most one. ⭐ So both models coexist: the
built-ins answer "hide the text", user layers answer "hide the act 2 specials",
and neither has to pretend to be the other.

## 0. The evidence — three surfaces, three different answers

Measured in the code, 2026-10-01:

| Surface | Layers | Set by |
|---|---|---|
| **The screen** | **4** — plan, pools, focus, labels (+ rulers, print-only) | fixed toggles in `index.html`, read as `.checked` |
| **The DXF export** | **6** — `BASE`, `POSITIONS`, `UNITS`, `TEXT`, `DIMS`, `NOTES` | `dxf_bridge.DxfSheet.LAYERS`, assigned as the sheet draws |
| **The PDF export** | **0** | nothing — there is no optional-content group in `scaled_pdf.py` |
| **The plot file** | **0** | no `layer` field on any object; `grep` finds none |

🔴 **The two that exist do not agree, and cannot.** `pools` and `focus` can be
switched off on screen and **have no DXF layer at all** — they are never written
to the DXF, so a CAD reader cannot turn them off because they were never there.
`POSITIONS` and `UNITS` are separable in CAD and **cannot be hidden on screen**.
Only two concepts appear in both, and even then under different names: plan/`BASE`
and labels/`TEXT`.

⭐ **So "add layers" is not adding a thing that is missing. It is choosing which
of two existing answers wins, and whether a third replaces both.**

---

## 1. What #82 is asking for is the third answer

"Different objects can live on layers" is **assignment**: an object carries a
layer, a person decides which, and the set of layers is open. That is the CAD
model — and it is what the DXF *import* already assumes, because it offers the
venue's own layer names to pick from (`import_dxf(..., layers=["WALLS","GRID"])`).

Both existing schemes are the opposite: **layers by KIND**, fixed, with nothing to
assign and nothing to get wrong.

| | By kind (what exists) | By assignment (#82) |
|---|---|---|
| Who decides | the program | the designer |
| Set of layers | fixed, 4 or 6 | open |
| Work per object | none | one decision, every time |
| Migration | none | every existing file |
| Can express | "hide the text" | "hide the act 2 specials" |
| Cannot express | "hide the act 2 specials" | nothing — but you must maintain it |

---

## 2. ⚠ What a designer actually reaches for

Worth being honest about the use cases before building for them, because the
expensive model is only worth it if the cheap one cannot do the job.

**Things by KIND handles:**

- "Turn the pools off, I am reading the ground plan." ✅ already works
- "Print without the focus leaders." ✅ already works
- "Give the shop the positions and units without my notes." ✅ in DXF today

**Things by KIND cannot do, and a designer asks for:**

- **"Show me the act 2 additions."**
- **"The dance plot, not the play plot"** — one rig, two shows, shared positions.
- **"Everything Jairous is hanging on Thursday"**, versus the FOH call.
- **"Hide the rep plot so I can see what I added."** ⭐ This one is already real
  here: a rented black box arrives with a house rep plot up, and
  `our-clients.md` says the Bluver likely will. Telling *my* units from *theirs*
  is a live problem in November, not a hypothetical.

🔴 **Every one of those is about INSTRUMENTS, not about drawing elements.** None
of them wants to hide the room, the text or the dimensions. That is the strongest
signal in this document about what to build.

---

## 3. ❓ And they may not be layers at all

If the real asks are all "show me this subset of units", then a **saved filter**
answers them without a layer system:

> Show: ⬢ all · ○ purpose contains "act 2" · ○ position = GRID C..D · ○ added by me

- **Nothing to assign.** It reads fields every instrument already has — purpose,
  position, channel, type, colour.
- **Nothing to migrate.** It works on every plot ever saved, today.
- **Cannot go stale.** A layer is a second place the truth lives and a second
  thing to keep right; a filter is derived, so it cannot disagree with the rig.

⚠ **What it cannot do** is express a grouping that is not already in the data. "The
units I am moving to the balcony tomorrow" is not a field — it is a thought, and
only an assigned layer can hold it. So the question is whether the groupings
designers want are **derivable or arbitrary**, and the honest answer is: mostly
derivable, occasionally not.

➡ **A middle path exists:** add ONE free-text field to an instrument — call it
`tag` — and let the filter read it alongside purpose and position. Arbitrary
grouping, one field, no layer system, no migration, and the paperwork can print
it. This is close to how a real-world instrument schedule already works: there is
always a column somebody is using as a grouping.

---

## 4. What a real layer system would touch

Scoped honestly, because "add a layer field" is the smallest part of it.

1. **The file.** A `layer` on every object that can be hidden, plus a `layers`
   list for their names, order and visibility. ⚠ `formatVersion` is 1 and
   `isPlot` rejects anything else, so this is a format change with a migration.
2. **The reader.** Every plot saved before today has no layers. The rule has to
   be written down: a missing layer means one default layer that is always
   visible — never "invisible", or a file would open empty.
3. **The renderer.** It currently draws by kind, in one pass per kind. Layers mean
   drawing in layer order, and layer order is drawing order.
4. **The PDF.** ⭐ PDF has real layers (optional content groups), and nothing in
   `scaled_pdf.py` uses them. A layered PDF would let an electrician switch the
   rep plot off in Acrobat on the ladder. **That is the single most valuable
   thing on this list** and it does not need a layer *system* — it could ship
   with layers by KIND tomorrow.
5. **The DXF.** Already layered, by kind, with six names. If objects gain layers,
   these two schemes have to be reconciled or explicitly kept apart.
6. **The UI.** A panel: name, visible, order, maybe colour. Plus the existing
   four toggles, which either become layers or stay as they are and are then a
   second control for the same idea.

---

## 5. 🔴 The trap, named in advance

**A hidden object is still in the plot, and still in the paperwork.** Hide a layer
and the schedule, the hookup, the channel count and the load totals must all
decide whether those units exist. Three wrong answers are available:

- The drawing hides them and the schedule lists them → the paper disagrees with
  itself, and somebody hangs a unit that is not on the plot.
- Both hide them → **a circuit load is computed without them.** That is the one
  that trips a breaker on a Thursday.
- Export silently includes them → "I turned that off" and it printed anyway.

⚠ **This already has a precedent in the repo to follow.** The `rulers` toggle is
print-only and says so on its label; the pool plane goes *inert, not hidden*
because "a control that vanishes takes its explanation with it". **Visibility has
never been allowed to change a number here**, and layers must not be where that
starts.

---

## 6. ➡ The build order, smallest first

Given the decisions above, the order changes: layers go in the file, so the file
comes first and everything else reads it.

1. **The merged set, in the file, visible on screen.** The eight layers of the
   table above as a `layers` array, plus the renderer reading it. The four
   existing toggles become four of the eight, so nothing is lost and four new
   ones appear. ⚠ **A plot saved before today has no `layers`** — the reader
   must treat that as "all eight, all visible", never as "none", or an old file
   opens blank.
2. **The DXF follows**, writing the same eight names instead of its own six. Two
   of them — Pools and Focus — reach the DXF for the first time.
3. **The layered PDF**, by the proven route. ⭐ This is the one an electrician
   feels: switch everything off but positions and units, on a ladder, in Acrobat.
4. **User layers**, with a panel to add and reorder them, once the eight have
   been lived with.

⚠ **Step 3 does not depend on steps 1 and 2.** The PDF could be layered by kind
tomorrow, with no format change at all — so if the file work stalls, that value
is still reachable on its own.

## 7. What is still open

The four questions this section used to hold are answered at the top. What is
left is narrower, and none of it blocks step 1.

1. ✅ **ANSWERED — a hidden layer does NOT change the paperwork.** See the section
   below; it was the sharp one and it is settled.
2. **Does a unit belong to exactly one layer?** One is simpler and is what CAD
   does. More than one makes "the act 2 specials" and "the dance plot" both work
   for a unit that is in both, and makes deleting a layer harder to reason about.
3. **What happens to objects on a deleted user layer** — move to the default, or
   refuse while it has members? The second is safer and more annoying.
4. **Does the screen's layer panel replace the toggle group, or sit beside it?**
   Eight chips is a lot of toolbar — the group holds four today — and a panel is
   more room but one click further from the drawing.

---

## ✅ Layers do not touch the paperwork — settled 2026-10-01

Jerry, on reading §5:

> It all brings up a good point. I dont think layers affect instrument schedules
> and Channel hook ups in [the drafting package most of this industry uses]

⭐ **That is the answer, and it comes from the right place.** This is settled
practice in the tool every designer reading our paperwork already knows, and
matching it costs nothing. A worksheet reports what matches its criteria; whether
a layer happens to be switched on is a property of the VIEW, not of the rig.

⚠ *Reported from Jerry's own use of it rather than verified in published
documentation* — the vendor's help pages reachable from here describe generating
schedules and recalculating them, and say nothing either way about visibility. It
is recorded as his judgement, which on this is the better source.

**So the rule, plainly:**

> **Layer visibility is a property of the DRAWING. The schedule, the hookup, the
> channel count and the circuit loads always report the whole rig.**

🔴 **This is what keeps §5's trap shut.** A load computed without the units
somebody switched off is the failure that trips a breaker on a Thursday, and it
is now impossible by rule rather than by care.

### ⭐ And it forces a clean separation that was half-argued in §3

If layers cannot filter paperwork, then "give me a schedule of only my units, not
the house rep plot" needs a **different mechanism** — and that mechanism is the
`tag`-style field §3 proposed, read as criteria.

| | filters the drawing | filters the paperwork |
|---|---|---|
| **Layer** | ✅ | ✗ never |
| **A field on the unit** | — | ✅ |

That is not a compromise between the two ideas in this document. It is both of
them, each doing the half it is good at, and the line between them is now a rule
rather than a judgement call.

⚠ **One consequence to put in front of the reader rather than let them find it:**
hide the rep plot, print a schedule, and the house units are still listed. That
is correct and it will still surprise someone. The schedule should say what it is
reporting — "all 47 units" — so the count is the hint.


---

## ✅ Step 1, as built — 2026-10-01

The eight layers are in the file, the renderer reads them, and six have chips.
Three things in the plan above turned out to be wrong when built, and they are
recorded here rather than quietly corrected upstream.

### ⚠ 1. There is no format change, and no migration

§4 said: *"`formatVersion` is 1 and `isPlot` rejects anything else, so this is a
format change with a migration."* **It is not.** `layers` is optional and purely
additive:

- An old file has no `layers`, and every layer takes its default.
- A file written here opens in an older build, which ignores the field and draws
  by its own toggles.

Nothing is lost in either direction, so `formatVersion` stays **1**. Bumping it
would have made every plot ever saved unopenable in order to buy nothing.

✅ **And the migration is exercised for real, not just in a test.** Every plot
file in the repository — the demo, the test fixtures, the saved plots — has no
`layers` key, so opening any of them runs this path. Checked by opening the app:
15 units, 9 positions, 24 labels, 20 pools, all drawn, chips all on.

### ⚠ 2. Six chips, not eight

§6 step 1 asked for the four toggles to become eight. **`dimensions` and `notes`
have no chip**, because the screen draws neither — the rulers and the key exist
only in the exported PDF. A chip that changes nothing visible is a control that
lies, and this repository already decided that case the other way round for the
pool plane: *"a control that vanishes takes its explanation with it."* Both
layers are still carried in the file and read by the export, so step 2 does not
have to touch the format again.

⭐ **`rulers` stopped being a special case, as §6 wanted.** It was the last
display toggle with its own private checkbox. It is now the `dimensions` layer,
read and written by the Export menu — and *saved with the plot*, which it never
was before.

### ⭐ 3. A label needs the thing it names

Not in the plan, and found while building. The merged set puts position names on
**Labels**, which is right — that is where the DXF puts text. But hiding
**Positions** while **Labels** stays on then prints a name over empty paper.

So text draws only when its own layer AND its subject's layer are on: a position
name needs `labels && positions`, a unit's channel needs `labels && units`.
Measured in the app: hiding **units** took 15 unit labels with it and left all 9
position names; hiding **positions** did the reverse.

⚠ **Pools and focus are deliberately NOT gated on units.** Where a unit's light
lands is worth drawing with the symbols off — the same reasoning that already
draws a boom's pool while drawing no symbol for it.

### 🔴 The cost, stated plainly: a toggle now dirties the plot

Layer state lives in the file, so switching a layer off is an edit. Peek at the
plot with the pools off and it says **Unsaved changes**. That is the price of the
decision at the top of this document — a state that does not survive reopening is
not in the file — and it is what every CAD package does. It is undoable, so an
accidental toggle costs one undo.

### What step 1 did NOT do

- The **DXF still writes its own six names** (step 2). Pools and Focus still
  reach no DXF layer.
- The **PDF still has no optional content groups** (step 3), which §6 calls the
  single most valuable item on the list and which does not depend on this work.
- **No user layers, and no reordering** (step 4). Array order is draw order and
  is seeded fixed, which is the shape a reorder will need.
- The three questions in §7 are still open and still do not block anything.
