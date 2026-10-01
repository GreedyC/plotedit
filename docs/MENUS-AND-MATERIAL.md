# The menus, the toolbars, and what Material actually says

**Status: PLAN. Nothing here is built.** Written 2026-10-01 for #56, at Jerry's
request:

> The menus are very standard - research the material standards and come up with
> a plan before implementation. read through the guides and examples at
> https://m3.material.io/

and:

> the look and feel and order are probably the weakest part of the app

He is right, and this document tries to say *why* in numbers rather than taste,
because "looks inconsistent" is not something anyone can build against.

➡ The tokens are already here. `index.html` has carried M3's colour **roles**,
type scale, elevation levels and shape scale since 2026-09-24. **What is missing
is the component and layout half**, which is what this is about.

---

## 0. The evidence, measured

Every interactive control in the two toolbars, measured in the running app:

| | |
|---|---|
| Controls in the two toolbars | **20** |
| Meeting M3's 48×48 minimum target | **0** |
| Distinct control heights | **3** — 16px, 28px, 32px |
| Checkbox **labels** (the real target) | 28px tall — passes WCAG 2.2 AA's 24, fails M3's 48 |
| `<select>` elements styled by the OS, not by us | **5** |
| Buttons built in TypeScript | **7** |
| …of those carrying any style class | **2** |

⚠ **Corrected 2026-10-01, before building from it.** An earlier draft said the
five class-less buttons "render in the browser's default chrome". **They do not.**
Measured in the app: Roboto, `--primary` green, pill radius, transparent
background — the global `button` rule reaches them, so they are M3 **text**
buttons, which is a real M3 variant.

🔴 **What is actually wrong is subtler and still worth fixing: there is no
emphasis.** In a position row, `+ unit`, `draw`, `renumber`, `number by clicking`
and `delete` are all the same weight, so nothing says which is the ordinary thing
to do. M3 gives five emphases precisely so a group can answer that, and
`index.html` already defines `filled`, `tonal`, `outlined` and `danger` — they are
simply not applied.

⚠ And `.pos-actions button { height:28px; padding:0 12px; font-size:12px }` is a
local rule that **duplicates `.small` exactly**, which is how the panel ended up a
third height. The class existed; the rule was written again beside it.

⚠ **Corrected 2026-10-01.** An earlier draft said five checkboxes fail WCAG 2.2
AA. **They do not.** The `<input>` is 16×16, but it sits inside a clickable
`<label>` that is **28px tall**, and the label is the target. Measured in the app.

So the accurate statement is narrower and less alarming: **nothing here fails
WCAG's 24×24 floor; everything fails M3's 48dp.** That 48 is a *touch* figure, and
this is a dense desktop drafting tool — which is an argument for M3's own
technique of keeping the visual size and expanding the hit area, not for making
every control 48px tall and stealing the drawing's space.

🔴 **Twice now a claim in this section has been measured on the wrong element** —
the buttons, and these labels. Both times the mistake was reading the control
rather than the thing a person actually clicks. Anything else here is suspect
until it has been measured the same way.

---

## 1. What M3 says, including the part that settles #56's own contradiction

#56 asks for two things that pull against each other:

> new, save, save as, open should be the same type - probably buttons

> the export menu is confusing it should be indented as In: Export / Plot PDF /
> Plot DXF

Make everything a button and Export has nowhere to put its list. Keep Export a
menu and the four file controls are not "the same type". **M3 resolves it
directly**, from *Menus → Usage*:

> Use a menu to show a temporary set of actions.

— and, for anything that should be on screen the whole time, a toolbar instead.

So the test is not what a control looks like, it is **whether the action is
always available**:

- **New, Save, Save As are always available** → buttons in the toolbar. Same
  type, as asked.
- **Open and Export are lists that grow or nest** → menus, opened *from* a
  button. Also as asked, and the indent is what a menu is.

That is one rule covering both halves of the request, and neither half has to
give way.

### The other rules this plan leans on

Paraphrased from the M3 guidelines, with the page to check each against. ⚠ Read
the source before building from this table — it is a summary, and a summary is
the thing that goes stale.

| Page | What it says, in short |
|---|---|
| [Menus](https://m3.material.io/components/menus/guidelines) | Group items with dividers — the gap treatment is not available on web. An item that does not currently apply is **disabled, not removed**. Submenus open beside the parent item, and are a web feature. |
| [Buttons](https://m3.material.io/components/buttons/guidelines) | Five styles, in order of emphasis: elevated, filled, filled tonal, outlined, text. Labels in **sentence case**, ideally one to three words, never wrapped. Too many buttons flattens the hierarchy — demote the low-priority ones to an overflow menu or an icon button. Outlined buttons read as chips; prefer filled or tonal where they sit near other bordered things. |
| [Toolbars](https://m3.material.io/components/toolbars/guidelines) | A minimum **48×48dp** target for every element. Do not crowd a toolbar; when the actions stop fitting, move them into a menu. A docked toolbar spans the window and keeps square corners. |
| [Switch](https://m3.material.io/components/switch/guidelines) | Switches suit standalone settings whose effect is immediate and needs no save. Checkboxes suit picking several related options from a list. Opposing choices — one of a set — belong in a connected button group, not a switch. |

---

## 2. The problems, each with the rule that decides it

### 2.0 🔴 The top bar, and the question of a File menu

> Is there a spec in material for menus like the file menu or edit menu?

**No. Material Design 3 has no menu bar.** Its full component list was checked
for this on 2026-10-01: the phrase *"menu bar"* does not appear on it. The
menu-shaped components are **Menus**, **Split buttons** and **FAB menu**.

⚠ **An earlier draft of this document gave the wrong reason** — that M3 is
"phone-first" and does not cover desktop. That was out of date by five months.
**Google I/O, 19 May 2026** shipped an expressive layout system whose breakpoints
run to **Large (1200–1599dp)** and **Extra-large (1600dp+)**, both labelled
*Desktop*, and which the page says apply to **"Android and web"**. There is now an
adaptive scaffold, an 8dp spacing system and guidance per breakpoint.

So M3 covers desktop deliberately, and *still* has no menu bar. **That is a
choice, not a gap** — which makes it worth weighing rather than working around.
At this app's window size (Large or Extra-large) M3's own recommendation for a
set of actions is a **toolbar**, with **menus** for anything supplemental.

⭐ One caution from the breakpoints page lands squarely on #56, which asks for the
file controls to be "the same type" and for Export to be a menu:

> Don't arbitrarily swap components that aren't functionally equivalent, such as
> swapping a button with a menu

Which is the same rule as §1, from the other end: **what the control *does*
decides what it *is*.**

⭐ **But a standard for it does exist — it is just not Google's.** The W3C's
[ARIA Authoring Practices menubar pattern](https://www.w3.org/WAI/ARIA/apg/patterns/menubar/)
describes exactly this: a visually persistent menu *"similar to those found near
the top of the window in many desktop applications"*. It specifies the roles
(`menubar`, `menu`, `menuitem`, `menuitemcheckbox`), `aria-haspopup` and
`aria-expanded` on anything with a submenu, and the keyboard contract — arrow
keys move within and between menus, Tab leaves the whole bar, Escape closes,
typing a letter jumps to an item.

So the two standards cover different halves, and they compose:

| | |
|---|---|
| **Structure and keyboard** | W3C ARIA APG — menubar pattern |
| **Look, type, colour, elevation, targets** | M3 tokens, already in `index.html` |

#### The fork, and it is Jerry's call

**A. A real menu bar.** `File  Edit  View  Export  Help` across the top, ARIA
pattern underneath, M3 tokens on top. Familiar to anyone who has used a drafting
package, and it would free the toolbar completely.

⚠ What it costs: **a menu bar earns its keep by hiding a large command surface.**
This app has about fifteen actions in total — four file, five export, five display
toggles, a handful of zoom. A menu bar would put a click in front of controls that
are currently one click away, and the two most-used (Save, zoom) would be the ones
that got slower. Menu bars are also the least touch-friendly pattern there is.

**B. M3's own answer to the same problem**, which is a toolbar of buttons where
the ones with lists open menus. From *Split buttons → Usage*: they

> add a menu of actions alongside a main action

which is precisely the Save / Save As / Revert shape. Concretely, row one becomes
four controls instead of seven:

```
 ↶ ↷ │  New      Open ▾      Save ▾      Export ▾
                 └ a menu     └ Save as…  └ Plot PDF, Plot DXF,
                   of plots     Revert      Schedule, Hookup, Eos…
                                            Sheet ▸  Scale ▸
```

- **New** — a plain button; always available, so by §1 it stays on screen.
- **Open ▾** — a button opening a menu, with *"Comes with plotedit"* as a real
  divider-separated group.
- **Save ▾** — a **split button**: pressing the label saves, pressing the chevron
  opens Save As… and Revert. It is already disabled when there is nothing to save,
  which is M3's rule for an item that does not currently apply.
- **Export ▾** — one menu, with Sheet and Scale as submenus (or a dialog — §9).

That is "all the same type" as #56 asked, **and** Export is indented, **and** the
row loses three controls.

⭐ **B is the recommendation**, for the reason in the warning above: fifteen
actions do not need a menu bar, and the two things a designer touches most would
get slower. But A is a legitimate reading of #56 and of how drafting tools
usually look, so it is written down rather than quietly dropped.

#### Either way, the second row is the other half of "awkward"

Two rows of chrome sit above the drawing. Row two is an import button, five
16×16 checkboxes, a select wedged between two of them, a print-only control among
screen-only ones, and the zoom cluster — five unrelated jobs in one line (§2.4).
M3 has a component for most of it: **segmented buttons**, which the components
list describes as being for switching views, and which would turn five identical
checkboxes into one group of icon toggles that reads at a glance and meets the
48px target.

**Fixing row one without row two leaves the app still looking like two toolbars
stacked.** They are one job.

### 2.0b Where Material sits, and the standard that is above it

Jerry, 2026-10-01: *"Isnt there something that has material as a decendant, or is
it the other way around."*

Both directions exist, and it is worth writing down once because it decides what
we are allowed to lean on.

```
        W3C ARIA APG · Open UI · Design Tokens (DTCG)      ← standards ABOVE
                          │
                   Material Design 3                       ← the system
                          │
   Material Web · Angular Material · MUI · Vuetify · Flutter   ← DESCENDANTS
```

**Above** are the vendor-neutral standards Material is an instance of. **Below**
are implementations of Material in a particular framework. Beside it sit the peer
corporate systems — Fluent, Carbon, Primer, Spectrum.

⭐ **The one above that matters for #56 is [Open UI](https://open-ui.org/).** It is
the W3C community effort to standardise what Material, Fluent and Carbon each
invented separately, and its first big win is landing in browsers now:
**`appearance: base-select`**, which lets a native `<select>` be styled completely
— the button, the popup, the chevron, the checkmark — *while keeping the native
keyboard behaviour and accessibility*.

That is almost exactly the fix §2.1 wants, for free.

🔴 **And we cannot rely on it, for a reason specific to this app.** MDN:

> This feature is not Baseline because it does not work in some of the most
> widely-used browsers.

It is Chrome and Edge today, with Firefox and Safari implementing. And
`server/serve.py` opens the app with `webbrowser.open(url)` — **the designer's
DEFAULT browser**, which on a Mac is frequently Safari. So adopting it would make
the app look like M3 on one machine and like the OS on the next.

⚠ **The complaint is inconsistency. A fix that is itself inconsistent across
browsers is not a fix.** It falls back gracefully, so it is a fine *progressive
enhancement* to add on top of a decision — but it cannot be the decision.

**Where that leaves the five selects:** they split in two, and the split is the
same one §1 drew.

| | | |
|---|---|---|
| `page`, `scale`, `poolplane` | genuinely hold a **value** | stay `<select>`, styled by hand now, with `base-select` added as an enhancement |
| `open`, `export` | fire an **action** and reset themselves | become buttons that open menus — §2.2 |

That is a smaller job than the first draft of this plan assumed, and a more
honest one: we stop fighting the two that were never selects, and keep the three
that were.

### 2.1 🔴 Five OS-styled `<select>`s sitting among M3 buttons

`open`, `export`, `page`, `scale`, `poolplane`. A native select draws itself with
the operating system's chrome — its own height, corner radius, focus ring and
chevron — none of which is in our token set. They are the loudest inconsistency
on the screen and the easiest to describe: **they are the controls that do not
match**.

Two of them are not even holding a value (§2.2).

### 2.2 🔴 Export is a `<select>` pretending to be a menu, and the code admits it

```
$("export").addEventListener("change", …)
  sel.value = "";          // ← reset, because it is not holding a value
```

**A control that clears itself after every use is not a value control.** It is a
menu wearing a select's clothes, and that is precisely what Jerry's "indent"
request is asking to be fixed. Open has the same shape.

### 2.3 ⚠ Sheet and Scale are export settings that live outside Export

> Choosing a paper and scale for printing is a bit confusing

They sit in the top toolbar beside the file actions, so they read as app state.
They are neither: **they affect the exported PDF and nothing else.** The screen
drawing ignores both.

And they are not independent of each other. **Fit** means *"the largest standard
scale at which nothing runs off the chosen sheet"* — so changing the sheet can
silently change the scale. Two menus that look parallel, one of which quietly
drives the other, sitting four controls away from the action they belong to.

### 2.4 ⚠ The toggle row is four kinds of control in one line

```
[Ground plan…]  ☐ plan  ☐ pools  at [head 5'-6"▾]  ☐ focus  ☐ labels  ☐ rulers (print)  zoom ▭────  [⛶][↕][↔][100%]
```

- **An import action** leads a row that is otherwise about display.
- **A select is wedged between two checkboxes**, so "pools / at / focus" reads as
  three peers when "at" belongs to "pools".
- **`rulers` is print-only** — the screen never draws them — sitting among four
  toggles that are all screen-only.
- Five 16×16 checkboxes, the smallest targets in the app.

M3's reading: these are standalone display settings taking effect immediately,
which is switch or **toggle-button** territory, not checkbox. Toggle buttons also
get the icon treatment M3 describes — outlined icon when off, filled when on —
which is far more scannable at a glance than five identical squares.

### 2.5 A separate finding: the panel order contradicts our own manual

⚠ **This is not what #56 means by "order"** — Jerry, 2026-10-01: *"I didnt mean
the order of the panels on the side - the menus along the top seem awkward."*
That is §2.0. This is kept because it is true and cheap, not because it was
asked for.

The right-hand panels, in DOM order, **all four `open`**:

```
Show & Venue   →   Instrument   →   Positions   →   Schedule
```

`docs/MANUAL.md` §3, *"A plot from nothing"*, teaches this order:

```
Say where you are  →  Bring in the ground plan  →  Build the positions
                   →  Hang units  →  Point them
```

**Instrument sits above Positions, but you cannot have a unit before you have a
position to hang it on.** The panel a new user meets second is the one they
cannot use yet. The manual is right and the UI is wrong; this is the "order"
complaint, and it is free to fix.

Jerry, in #56's comments:

> We can also have the show and venue tab close on start-up

Agreed, and it generalises: **four open accordions is not an order, it is a
wall.** Open the one you are working in.

### 2.6 ⚠ The panel buttons are unstyled, and the labels are in four cases

Seven buttons are built in TypeScript; two get a class. And the labels:

```
+ Add position    + unit    Delete instrument    delete    draw    renumber    number by clicking
```

Title Case, lowercase, and a mix, in two panels. M3: **sentence case, 1–3 words.**
So: `Add position`, `Add unit`, `Delete`, `Draw`, `Renumber`, `Number by clicking`.

⚠ And one name that is actively misleading rather than merely untidy: **`.pos-row`
is the class on Show & Venue's fields as well as on position rows.** Writing to
"the first `.pos-row`'s third input" lands in **Designer**, not a trim — which is
exactly what happened while testing this release, and the value reached a file
before it was noticed. A class that does not mean what it says is a trap for
whoever reads it next.

---

## 3. The two rows, drawn out

Jerry, 2026-10-01, on the second row:

> The plan, pools, focus, and labels checkboxes are just strewn across. Maybe we
> can group them by function? the drawing zoom, and the icons to the right seem
> to make sense together but maybe we could group them somehow. The open could be
> a button with a dropdown? Maybe allow people to change directories? Same thing
> with export. we use a button for the ground plan. but we could move that to the
> end of the buttons. Can we do tool tips on the buttons?

### 3.1 Row one — what the file is

```
 ↶ ↷ │  New    Open ▾    Save ▾    Export ▾   │   Ground plan…
                 │          │          │
                 │          │          └ Plot PDF · Plot DXF · Schedule ·
                 │          │            Hookup · Eos patch
                 │          │            ──────────────
                 │          │            Sheet ▸   Scale ▸   ☐ Rulers
                 │          │
                 │          └ Save as…   Revert
                 │
                 └ (recent plots)
                   ──────────────
                   Comes with plotedit ▸
                   ──────────────
                   Change folder…
```

- **Open ▾ and Export ▾ become buttons with menus**, as asked. §1 is why that is
  also the correct answer rather than merely the asked-for one.
- **Save ▾ is a split button** — press the label to save, press the chevron for
  Save as… and Revert. It is already disabled when there is nothing to save.
- **Ground plan… moves to the end of row one**, as asked. It is a file action; it
  was only ever in row two because row two is where things went.
- **Sheet, Scale and Rulers move inside Export**, which is the only thing any of
  them affect (§2.3). Rulers leaves row two, where it was the one print-only
  control among screen-only ones.

### 3.2 ⭐ Row two — they are not four functions, they are one

> Maybe we can group them by function?

Worth saying plainly: **plan, pools, focus and labels are all the same function.**
Each one shows or hides a layer of the drawing. That is why the answer is *one*
group rather than several — grouping them by function groups all four together.

```
 Show  [ plan │ pools │ focus │ labels ]  at [head 5'-6" ▾]   │   Zoom [──▭────] [⛶][↕][↔][100%]
```

- **One connected toggle group** for the four layers, which is what M3's segmented
  and toggle buttons are for — an outlined icon when off, filled when on, so the
  state reads at a glance instead of as four identical ticked squares.
- **`at …` attaches to pools**, because it is not a fifth peer: it says what height
  the pools are cut at. Today it sits between *pools* and *focus* and reads as one
  of them. ⚠ And when pools is off it should go **disabled, not hidden** — the
  rule already settled in `DECISIONS.md` for inert fields, and M3's rule for menu
  items that do not currently apply.
- **The zoom cluster becomes one group**, as asked: the slider and the four
  buttons are one control for one thing, so they get one label and one container.

That is five things in row two instead of eleven, and every one of them is at
least 48px.

### 3.3 Tooltips — yes, and 11 controls have none

> Can we do tool tips on the buttons?

Measured: **29 controls in the two bars, 11 with no tooltip at all** — and they
are almost exactly the row this section is about. Every control in row one has
one. The five display checkboxes, the pool plane, the zoom slider and the five
backdrop fields have none; `rulers` only has one because its parent label does.

M3 splits them, and the split matters here:

- **Plain tooltips** label an element that has no text — the icon-only buttons:
  undo, redo, and the three zoom icons. ⚠ M3 is explicit that a plain tooltip is
  **not needed when the element already has label text**, so New, Save and Save
  As… do not want one.
- **Rich tooltips** carry a sentence or two of explanation.

🔴 **The app already writes rich-tooltip content into `title`.** The Sheet
selector's tooltip is a full paragraph about ARCH, ANSI and A-series stock; the
rulers one explains that the screen never draws them. Native `title` renders
those as an unstyled OS box after a delay you cannot control, and on no touch
device at all. They are the best text in the toolbar and they are in the worst
container.

⚠ And M3's caution applies to one of them already: *do not hide critical
information in a tooltip*. "The screen never draws these" is critical — it is why
the checkbox looks like it does nothing — so it belongs in the label, which is
what `(print)` is doing, and the tooltip can explain the rest.

### 3.4 Changing folders — move the fence, do not open the gate

> Maybe allow people to change directories?

Workable, and the server is the piece that makes it possible: a browser cannot
browse a filesystem, but `plotedit` ships its own Python server, and `/plots`
already reports its `folder`.

🔴 **But it must be built as a change of root, never as a relaxation of
`store.resolve`.** That function is careful on purpose, and its docstring says
why:

> Checked BOTH ways: the name is matched against a pattern, and then the resolved
> path is required to sit inside the plots directory. The pattern alone would be a
> promise about a regex; the containment check is a fact about the filesystem.

So: **`root()` becomes settable at runtime** — it already reads `PLOTEDIT_PLOTS`,
so the idea of a configurable root exists — and `resolve()` keeps enforcing
containment inside whatever root currently is. Every guard that exists today
keeps working, and a plot name still cannot escape its folder.

⚠ Open question in §9: picking a folder needs *some* way to name one, and a text
box inviting a path is the thing that makes a traversal bug likely. A list of
folders the server offers — recent, plus any subfolder of the current root — is
narrower and probably enough.

## 4. Revert — mostly built already

> We should possibly add a revert to return the file to the way it was before we
> touched it in this session

`adoptPlot` already builds a fresh `Store` from the loaded plot, and `dirty` is
literally `_seq !== _savedSeq`. **The opened state is something the store already
knows.** What is missing is keeping the opened JSON so Revert is one step rather
than walking the undo stack.

⚠ It must ask first, and the dialog must say what is lost — `confirm.ts` already
sets that pattern, and its rule applies: name the thing, say what goes with it.

---

## 5. What to build, smallest first

Each step stands alone and is worth shipping by itself. **None of them needs a
component framework** — see §8, and §6 for why there is no such framework for
the web anyway.

1. **Give every TypeScript-built button a style class, and the labels sentence
   case.** One afternoon, no layout change, and it removes the single most
   visible inconsistency. Guard it with a test that no `createElement("button")`
   ships without a class.
2. **Raise every target to 48×48**, or to 24×24 at the absolute minimum where the
   toolbar cannot afford it. The checkboxes are the urgent ones — they fail WCAG.
3. **Split the five `<select>`s two ways, per §2.0b.** `open` and `export` become
   buttons opening M3 menus — dividers, disabled items rather than missing ones,
   submenus where the content nests. Export gets its indent; Open gets its
   *"Comes with plotedit"* group as a real group. `page`, `scale` and `poolplane`
   stay selects and get styled, because they hold values.
   ⚠ `appearance: base-select` only as an enhancement on top — it is Chrome-only
   today and this app opens in whatever browser the designer defaults to.
4. **Move Sheet and Scale into Export**, as a submenu or as the first thing the
   export sheet asks. State the Fit interaction in words where it is chosen, so
   changing the sheet never silently changes the scale without saying so.
5. **Rebuild the second toolbar** as: import on the left with the other file
   actions or on its own; a connected toggle-button group for the display layers,
   with `at …` attached to `pools` rather than floating between peers; `rulers`
   moved to where print settings live, which is now Export; zoom alone on the
   right.
6. **Reorder the panels to the manual's order** — Show & Venue, Positions,
   Instrument, Schedule — and open only one at a time, starting on Positions for
   a plot that has some and Show & Venue for one that does not.
7. **Revert**, per §4.
8. **Rename `.pos-row`** where it is not a position row.

---

## 6. 🔴 The components this plan recommends have NO web implementation

Checked on each component's own availability table, 2026-10-01:

| Component | Figma | Compose | Android Views | **Web** |
|---|---|---|---|---|
| **Split button** | ✅ | ✅ | ✅ | **✗ unavailable** |
| **Menus — Expressive** | ✅ | ✅ | ✗ | **✗ unavailable** |
| Menus — baseline | ✅ | ✅ | ✅ | ✅ |

**The newest and most useful parts of M3 exist as design guidance, a Figma kit,
and Android/Flutter code — and nothing for the web.** Material Web, Google's own
web implementation, is separately
[in maintenance mode pending new maintainers](https://github.com/material-components/material-web).

⭐ **This is not a reason to abandon the plan. It is the reason the plan is
written the way it is.** We were never going to install these components, because
for the web they do not exist. The guidance is published, specific and free to
read; the code is the part that is missing, and the code is the cheap part.

⚠ It does mean two honest consequences:

1. **Anything built here is ours to maintain.** A split button is roughly a
   button, a chevron and a menu — small. Reading the Specs tab before building
   each one is not optional, because this document is a summary and summaries go
   stale.
2. **"Use the Material library" is not an option anyone can take**, so if the
   answer to "should we adopt a component library" is yes, it will not be
   Google's — it would be MUI, Angular Material or similar, which means adopting
   their framework too. §7 and §8.

## 7. Bootstrap, Tailwind, and what would actually help

Jerry, 2026-10-01: *"I was thinking of Bootstrap - would Tailwind help us?"*

### Bootstrap — closer to the ask than Tailwind, and still wrong here

Bootstrap is the thing that fits the description: it ships a **navbar with
dropdowns**, **button groups** and **split buttons**, with the JavaScript
behaviour included. It is genuinely the shortest path to the bar in #56.

🔴 **But it is a different design language, not a layer on Material.** Adopting it
means adopting its look — its palette, its radii, its type scale — and this app
has a brand-derived M3 token set built from the logo, which the brand rules pin
down by name. We would be running two design systems and picking a winner on
every component. Its reset also applies to the whole document, including the SVG
drawing surface.

### Tailwind — would not help with this problem

Tailwind is a **utility-class** framework. It ships `flex`, `p-4`, `text-sm` and
nothing else: **no menu, no split button, no toggle group, no focus management.**

Line up what #56 actually needs against what Tailwind provides:

| What is wrong | Would Tailwind fix it? |
|---|---|
| 5 of 7 panel buttons have no style class | No — it changes *where* the styles are written, not whether they exist |
| 20 of 20 controls under the 48px target | No |
| Export is a `<select>` that should be a menu | No — this is behaviour, not CSS |
| Open needs a grouped, dividered menu | No |
| Five display checkboxes should be one toggle group | No |

⚠ **And it would cost two things.** It is a second styling vocabulary beside the
M3 tokens already in `index.html` — tokens Tailwind would have to be reconfigured
to match, at which point it is our tokens with extra steps. And because the panels
are built with `createElement` in TypeScript rather than written as markup,
Tailwind styling arrives as long `className` strings inside TS, which is harder
to read than the CSS file it replaces.

⭐ **Neither framework is the lever, because the hard part was never the CSS.** It
is the *behaviour* of a menu: opening on a button, closing when you click away,
trapping focus, escaping, and sitting above everything else without being clipped
by a scrolling panel.

### What would actually help, and it is already in the browser

That behaviour stopped needing a library. Checked on MDN, 2026-10-01:

| | Status |
|---|---|
| **Popover API** (`popover`, `popovertarget`) | **Baseline since April 2025** — top layer, light dismiss, Escape, and the button/popup relationship, all free |
| **CSS anchor positioning** (`anchor-name`, `position-anchor`, `position-try`) | **Baseline since September 2026** — a menu tethered to its button that flips when it would run off screen |

Together those are the two things people used to install a library for. A menu
becomes a `<div popover>` anchored to its button; the top-layer stacking, the
outside-click dismiss and the reposition-when-clipped are the platform's job.

⚠ **Anchor positioning is one month old as Baseline**, so it is *newly* available
rather than *widely* — and this app opens in whatever browser the designer
defaults to (§2.0b). Treat it the way §2.0b treats `base-select`: build the menu
so it works positioned plainly, and let anchor positioning improve it where it is
supported.

**What is left to write by hand** is small, and it is the part no framework was
going to give us anyway: the ARIA roles and the arrow-key contract from the APG
pattern (§2.0), and the M3 look from tokens we already have.

## 8. 🔴 What not to do: do not pull in a component library

This was decided on 2026-09-24 and is worth restating, because "standardise on
Material" is exactly the request that invites it. From `index.html`:

> These are M3's own structures — colour ROLES rather than colour names, the type
> scale, the elevation levels, the state layers, the shape scale — written out
> rather than pulled in as a framework. **A component library would have to be
> fought at every point where this app is a drawing surface rather than a form.**

That still holds, and §6 strengthens it from an unexpected direction: **for the
web there is no Material component library to pull in.** Google's own is
unmaintained and does not carry the components this plan wants.

The app's centre is an SVG plot with its own pointer modes — calibrating, drawing
a pipe, numbering a run — and a library's event handling is the first thing that
would have to be prised off it. ⚠ It would also be a second install for a
lighting designer who currently needs only Python.

⚠ **The live question is therefore not "Material library or not"** — that one is
answered — **but whether to adopt a framework-bound library** such as MUI
(React) or Angular Material. That is a much larger decision than #56, because
this app has no framework at all today, and it is Jerry's to make.

**M3 is a specification here, not a dependency.** Everything in §5 is CSS and
plain DOM.

---

## 9. Open questions for Jerry

1. **Switches or toggle buttons for the display layers?** Switches are the
   literal M3 answer for standalone settings; a connected group of icon toggle
   buttons is far more compact and reads at a glance. The row has five of them,
   which is where compactness starts to matter.
2. **Should Export open a menu, or a dialog?** A menu matches #56 as written. But
   sheet, scale and rulers all belong to the export and would make a menu that
   carries settings — which the Menus page warns against — a menu item should
   carry one action, not embedded controls. A small **Export dialog** would
   hold all of it honestly. The menu is closer to what was asked; the dialog is
   closer to what the thing actually is.
3. **One panel open at a time, or just a sensible default?** Accordion behaviour
   is tidier and costs a click when you are moving between positions and the
   instrument panel, which is a thing designers do constantly.
4. **Is `rulers` the only print-only control?** If anything else on screen only
   affects paper, it should move with it rather than be found later.
5. **How should a folder be chosen (§3.4)?** A text box inviting a path is the
   thing that makes a traversal bug likely. A list the server offers — recent
   folders, plus subfolders of the current root — is narrower, and may be enough.
   Does it need to reach anywhere on the disk, or is "the folders I use" the real
   requirement?
6. **Do the four layer toggles keep their text labels?** A connected toggle group
   of icons is the most compact and reads fastest once learned, but `plan`,
   `pools`, `focus` and `labels` have no obvious icons and would lean on tooltips
   until they do. Icon plus label is wider but needs no learning.
