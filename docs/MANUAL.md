# plotedit — the manual

How to draft a plot with it, field by field and button by button.

This is the **how**. [README.md](../README.md) is the **what and why** — what it
draws, what it refuses to do, and how to install it. Start there if you have not
run it yet.

---

## Contents

1. [Starting and stopping](#1-starting-and-stopping)
2. [The screen](#2-the-screen)
3. [A plot from nothing](#3-a-plot-from-nothing)
4. [The instrument panel](#4-the-instrument-panel)
5. [Greyed-out fields](#5-greyed-out-fields)
6. [The numbers at the top](#6-the-numbers-at-the-top)
7. [Pools](#7-pools)
8. [Mouse and keyboard](#8-mouse-and-keyboard)
9. [Saving, opening, and where files live](#9-saving-opening-and-where-files-live)
10. [Exports](#10-exports)
11. [When it will not answer](#11-when-it-will-not-answer)
12. [When something goes wrong](#12-when-something-goes-wrong)

---

## 1. Starting and stopping

Double-click **`run.command`** (Mac) or **`run.bat`** (Windows). Your browser
opens on the editor.

**That is how you start it every time.** There is no separate launcher and
nothing to install after the first run.

⚠ **Leave the terminal window open while you work.** Closing it — or ctrl-C in
it — stops the program. The browser tab will still be there, but nothing will
save.

To stop: close the terminal window.

---

## 2. The screen

**The drawing is on the left, the panels on the right.** Drag the bar between
them to change the split; it remembers where you put it. The bar is also
keyboard-operable — tab to it and use the arrow keys, or Enter to reset.

### The top row

| | |
|---|---|
| **↶ ↷** | Undo and redo. A whole drag is one step, not fifty. |
| **New** | Start over. Asks before discarding unsaved work, then asks what the show is called. |
| **Open…** | Lists the plots in your plots folder. |
| **Save** / **Save As…** | ⌘S and ⇧⌘S. |
| **Export…** | See [§10](#10-exports). |
| **Scale** | Paper scale for the exported PDF. **Fit** picks the largest standard scale at which nothing runs off the sheet. ⚠ The list is imperial fractions on an imperial plot and metric ratios on a metric one, never both — offering ¼" on a metric plot would let you issue a drawing at a ratio your scale rule does not have. |

**Ground plan…** imports the venue — **DXF or PDF**. This never draws
architecture itself; the room arrives as a drawing somebody else made.

### The toggles

| | |
|---|---|
| **plan** | The imported ground plan under everything. |
| **pools** | The light on the floor. See [§7](#7-pools). |
| **at …** | Which plane the pools are cut at. |
| **focus** | The dashed leader from each unit to what it is pointed at. |
| **labels** | Colour, purpose, and the notation containers. |
| **rulers** | Margin rulers. Marked *(print)* because they are there for the printed sheet. |

### Zoom

The slider runs **2 to 40 pixels per foot**. The three buttons fit the whole
plot, the height, or the width. **100%** returns to 14 px per foot.

### The panels

**Show & Venue**, **Instrument**, **Positions**, **Schedule** — each collapses,
and the number on the right tells you how many of a thing there are.

---

## 3. A plot from nothing

### Say where you are

Open **Show & Venue** and fill in the show, venue, designer, revision and date.
These go in the title block.

Then **The Room**: width, depth, grid height, house ceiling, plaster line.

⚠ **Blank means "not known", and it is a real answer.** The checks say so out
loud rather than assuming zero — a grid height of 0 would be a claim that the
ceiling is on the floor.

**Units** — imperial or metric — changes every length in the app *and* the scales
offered for print.

**Control** is how the house gets power to a lamp, and it changes the notation
rather than just the data:

| | |
|---|---|
| **Dimmer per circuit** | Most houses. The circuit is hard-wired to its own dimmer, so the two are **one number** and the plot draws one hexagon. Drawing two containers here is not harmlessly tidy — it tells the electrician there is a patch to make, and there is not. |
| **Hard and soft patch** | Circuit, dimmer and channel all differ. All three containers. |
| **No soft patch** | The console addresses dimmers directly. |
| **Dimmer = address (ETC)** | A dimmer is one DMX address carrying intensity, so the dimmer number *is* the address. The hexagon carries the address, exactly as it does for an LED, and a mixed rig reads the same throughout. |

### Bring in the ground plan

**Ground plan…** → pick a **DXF** or **PDF** of the venue.

A **PDF** takes two more answers, because a PDF does not record either:

- **Which page**, if more than one has a drawing on it. It lists them with their
  sheet size and how many lines each holds. ⚠ A **scanned** plan has no vectors
  at all, and it says so rather than importing nothing and looking broken.
- **What scale that drawing is.** It is printed in the title block.

It then tells you how big the imported drawing came out:

```
1,284 paths at 1/4" = 1'-0" — 61.0' x 44.0' including the sheet border.
Check that against something you measured.
```

🔴 **Check it.** At the wrong scale the import is still a perfectly believable
drawing — just of a different building. That number is the only thing that
catches it.

### Build the positions

**Positions** → **+ Add position**. Each one has a name, a type —
electric, pipe, grid, catwalk, truss, boom, box-boom, ladder, tormentor — a trim,
and its ends.

A **vertical** position (boom, box boom, ladder, tormentor) is a *point* in plan:
every unit on it shares one x and y and is told apart by height. It also asks for
a **Mount**: boom base, floor plate or flange.

⭐ **Record the house's circuits on the position** if you know them. The app never
invents circuit numbers — they depend on the house and have no set order — but it
will check your plot against what you entered and tell you when a unit is on a
circuit that position does not have.

### Hang units

On a position, **+ unit**. **renumber** puts the units back in order along the
pipe (RP-2 §2.3.2) after you have been moving things about. **delete** removes the
position.

Then drag them where they go. A unit **snaps to the nearest pipe** as you drag;
**hold Alt** to place one deliberately off a pipe.

### Point them

Drag the **ring** — the focus handle — to where the light lands. The dashed
leader follows.

Or type it: **Focus X**, **Focus Y**, and **Focus height** (head height, 5'-6",
unless the light lands somewhere else).

### Colour and patch

See [§4](#4-the-instrument-panel).

---

## 4. The instrument panel

Click a unit — on the drawing or in the schedule — and the panel fills. The
fields are in the order you use them, not the order a database would put them.

| Field | |
|---|---|
| **Unit** | Its number on the pipe. |
| **Channel** | What the console calls it. |
| **Purpose** | What it is *for*. Right under the channel because that is what you read next. |
| **Circuit** | The **house** circuit. Never generated. |
| **Dimmer** | |
| **Address** | `45`, or `2/21` for a universe. The **start** address; the schedule prints the range. |
| **Model** | The specific fixture. Personalities differ between models, so the address range depends on this. |
| **DMX personality** | What the fixture is set to at its own display. Two identical units can be on different personalities. |
| **Type** | The fixture. ⭐ **The lens is part of the type** — a `Lustr 26 EDLT` and a `Lustr 36 EDLT` are different rows, which is why changing it resizes the pool. There is no separate beam-angle box to contradict it. |
| **Position** | |
| **Color** | A dropdown of **498 gels** — Roscolux and LEE — that you can also type into. `R52+R119` **stacks** (the transmissions multiply); `R52/R119` is a **split frame** (only the first counts). Neither is in any list, which is why this is not a plain dropdown. ⚠ A bare number is refused: `R119` is Light Hamburg Frost at 89% and `L119` is Dark Blue at 2%. |
| **Gobo** | |
| **Accessories** | Separate with `+` — "top hat + gobo". Gate accessories are drawn at the gate, front accessories at the nose; you say only what is on the unit. |
| **X / Y / Trim** | ⭐ Usually not typed — they arrive from dragging. The boxes are there to read back and to correct. On a **boom**, trim is the height on the boom and is written to both fields. |
| **Focus X / Y / height** | |
| **Lamp** | What is in it. A **Source 4WRD** retrofit is a lamp: same barrel, same lens, 150 W instead of 575. |
| **LED mode** | The **photometric** output mode — how bright. Not the DMX personality. |
| **Lens angle** | Oval-beam units only (PARNel): degrees the lens is turned. |
| **Notes** | |

**Delete instrument** is at the bottom, and it asks first.

---

## 5. Greyed-out fields

**A greyed field is a fact about the rig, not a fault.** Hover it and it says
why. It keeps its value; it just stops taking input.

| Field | Greyed when |
|---|---|
| **Lamp** | the fixture is an LED engine — there is no lamp in it |
| **LED mode** | it is not — it takes a lamp |
| **Dimmer** | the unit is patched as `Dimmer`, or the house is dimmer-is-address and it has an address |
| **Lens angle** | it is not an oval-beam unit |
| **Model** | no specific models are on file for that type |
| **DMX personality** | no personalities are published for it |

⚠ **A greyed field still shows what is in it.** If a Lustr somehow carries an
HPL 575, you will see it, greyed, with the reason. Hiding a wrong value is how it
survives to the load-in.

---

## 6. The numbers at the top

Above the fields, for the selected unit:

```
14'-8" throw · 35° · pool 6'-6"
147 fc   at HPL 575 (MF 0.78), through R52 26% + R119 89%
```

- **Throw** — unit to focus point, in three dimensions.
- **The angle** — how steep it is.
- **Pool** — the **field** across, at the plane you chose.
- **The level**, and **what it was computed from**. Note that it names the lamp
  multiplier *and* both gels with their transmissions, so you can check it.

On a metric plot that reads `4.5 m`, `38°` and `lx` — the unit follows the plot,
never a hardcoded "fc".

### When it cannot give you a level

The geometry still comes out; the level says why it did not:

```
18'-1" throw · 40° · pool 21'-4"
no candela on file for S4 90 — ETC Source Four 90° datasheet (angles);
candela not extracted
```

### When it cannot compute at all

```
Not computed — needs a trim height and a focus point
```

⭐ **Both of those are the app working, not failing.** A number it cannot justify
is a number it will not print.

---

## 7. Pools

**Ellipses, not circles.** A cone only cuts a circle when it points straight
down. At 30° a 26° field lands more than twice as long as it is wide, and the
long end is the one that reaches the scenery.

The **at …** menu cuts them at head height (5'-6"), a face (5'-2"), seated
(3'-6"), or the deck. Different planes are different plots: what covers a face
does not cover a floor.

---

## 8. Mouse and keyboard

### Mouse

| | |
|---|---|
| Click a unit | select it |
| Drag the **body** | move it — snaps to the nearest pipe |
| **Alt**-drag | move it without snapping |
| Drag the **ring** | re-aim it |
| A unit in a **boom elevation** | selects, but does not drag — the elevation is a diagram beside the plot, and its height is compressed |

### Keyboard

| | |
|---|---|
| **⌘Z / ⇧⌘Z** | undo / redo |
| **⌘S / ⇧⌘S** | Save / Save As… |
| **Arrows** | nudge by an **inch** |
| **Shift + arrows** | nudge by a **foot** |
| **Escape** | deselect |
| **Delete / Backspace** | delete the unit — **asks first** |

⭐ **Up the screen is upstage.**

### Typing measurements

Anywhere it shows a length it accepts one:

```
1'6"      1'-6"      1' 6"      18"      1.5
```

---

## 9. Saving, opening, and where files live

Plots go in a **`plots`** folder next to `run.command`, as `.plot.json`.

**Save** writes the file you are on. **Save As…** starts a new one. **Open…**
lists what is there.

To keep them somewhere else — a show folder, or Dropbox — set `PLOTEDIT_PLOTS`
to that path before starting.

⭐ **A plot is plain JSON.** Readable in a text editor, diffable, and still
openable in twenty years without a subscription. That is deliberate.

**"Unsaved changes"** by the show name means exactly that. Selecting a unit is
not a change; nor is typing a value back the way it was. Undo your way back to
what is on disk and it clears.

---

## 10. Exports

| | |
|---|---|
| **Plot PDF** | The drawing, to the scale chosen above. |
| **Plot DXF** | For anyone who needs it in CAD. |
| **Instrument schedule** | Position, Unit, Channel, Circuit, Dimmer, Address, Thru, Type, Wattage, Color, Gobo, Purpose, Accessory, Notes. |
| **Channel hookup** | The same rig in channel order. |
| **Eos patch** | ⚠ **Untested against a console.** Written to the USITT ASCII spec and nothing more. Treat it as a draft. |

⚠ **Exports refuse rather than clip.** If a drawing will not fit the sheet it
says which sheet to move to instead of quietly cropping it.

---

## 11. When it will not answer

The app says "I do not know" a lot, on purpose. **A figure on paperwork looks
exactly as authoritative whether it is right or wrong**, and the unit patched
into the tail of a wrong address range is the one nobody finds until tech.

So it will tell you, rather than guess:

- **A gel it does not have.** Diffusions especially — neither Rosco nor LEE
  publish transmissions for them on the web.
- **A fixture with no published candela.** Cyc units mostly. It still draws them
  and still gives you the paperwork.
- **A DMX footprint for a personality nobody documented.** It shows the start
  address and says why there is no range.
- **A circuit the house does not list** on that position, if you told it what the
  house has.

⚠ **It does not check clearance.** It draws the room and the rig. Masking,
scenery and rigging points are not in it, so a trim it accepts may still hang
into a border.

---

## 12. When something goes wrong

**It will not start.** The terminal window stays open on an error and says why.
On Windows, the usual cause is the Microsoft Store Python stub — install from
[python.org](https://www.python.org/downloads/) and tick *"Add python.exe to
PATH"*. On a Mac the first run may need right-click → **Open** → **Open**.

**A fixture draws as a plain ring.** It is a type the app does not know. It will
still take all the paperwork; it just has no symbol. See
[CONTRIBUTING.md](../CONTRIBUTING.md) — mapping an unknown name onto an existing
RP-2 family is one line and needs no drawing.

**A number looks wrong.** Hover it. Everything computed says what it came from.

**Reporting something.** The build number is in the top bar, by the show name.
Quote it.
