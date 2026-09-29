# Lamp and LED mode — an open discussion

**Status: DISCUSSION. Nothing here is decided, and nothing here is built.**
Opened 2026.09.29 at Jerry's request, after looking at the inspector panel:

> an HPL 575 can't have an LED mode. Also I believe an HPL by definition is
> 575W. There are 750s but aren't they a different designator?

Two questions. The second one has a documented answer, so it goes first —
because it changes what the first one should do.

---

## 0. 🔴 HPL is not a wattage. It is the lamp type, and it comes in four.

**ETC Source Four 26° datasheet, page 3, the "Lamps" table** — already the source
for the multipliers in `photometrics.py` — lists **22 HPL lamps**:

| | |
|---|---|
| Wattages | **375, 550, 575, 750** |
| Volts | 77, 115, 120, 230, 240 |
| Each in | standard and `X` (long life) |

Page 1 of the same sheet says what the designator actually means:

> HPL – compact tungsten filament contained in a krypton-[filled envelope]

So **HPL names the burner, not the wattage.** `HPL 750/115` is as much an HPL as
`HPL 575/115` — same base, same envelope, drops into the same barrel. The number
after it is the wattage and the number after the slash is the volts.

**This is already how the app models it**, and the numbers check out. The
datasheet gives the 26° Cd MF for `HPL 575/115` as **.78**, and
`LAMP_MF["HPL 575"]["S4 26"]` is **0.78**. It was read off this table correctly.

Two consequences worth naming:

- ⚠ **The dropdown offers 3 of 22.** `main.ts` hardcodes `HPL 750, HPL 575,
  HPL 575X`. There is no **HPL 375** — a real lamp, CdMF .66 at 26°, and the one
  you reach for on a small rig or a tight dimmer — and no **HPL 550/77**, which
  is the Dimmer Doubling lamp. A designer who owns those cannot record them.
- ⚠ **The three retrofit burners are missing too.** `Source 4WRD II`, `Gallery`
  and `Daylight Gallery` went into `LAMP_MF` in v0.1.19 and never reached the
  dropdown. The data is there; the list has not caught up.

**That is a real bug independent of everything below**, and it is the same bug
twice: *the list of lamps lives in the browser, and the lamps live in Python.*

---

## 1. The actual question: a lamp and a mode are never both true

Cross-tabulating `FIXTURES` against `LAMP_MF` and each fixture's `modes`:

| | has lamps | has modes |
|---|---|---|
| S4 19/26/36/50, EDLT, EA PAR | ✅ | — |
| Lustr, ColorSource Spot | — | ✅ |
| S4 Zoom, PARNel, cycs, SHEHDS | — | — |

**Not one fixture in the table has both.** The overlap is empty, and it is empty
for a reason rather than by accident: a lamp is *the thing making light*, and an
output mode is *how the thing making light is being driven*. A barrel with an
HPL in it has no menu. A Lustr has no lamp to order.

Today the panel shows **both rows on every instrument**, which is how you get an
HPL 575 sitting above an LED mode dropdown.

### ➡ Suggested position: one question, asked once, by the server

**Render whichever row applies to this fixture, and nothing for the other.**

The server already knows. `/fixtures` publishes each type's `modes`. It does
**not** yet publish which lamps have a multiplier for that type, and it should —
that is the `LAMP_MF` lookup, done in the one place that owns it.

```
/fixtures →  "S4 26":    lamps: [HPL 750, HPL 575, Source 4WRD II, …]  modes: null
             "Lustr 26": lamps: null   modes: [Boost Full, Regulated 3200K, …]
             "S4 Zoom 15-30 @23": lamps: null   modes: null
```

The inspector renders a Lamp row if `lamps`, a mode row if `modes`, neither if
neither. The contradiction stops being something to validate and starts being
something you cannot express.

This also fixes the ColorSource quietly: its modes are **Maximum Output**,
**At 3200K**, **At 5600K** — different names from the Lustr's four, which are
what the hardcoded list offers today.

### 🔴 The trap in hiding a row: the orphan

If a unit is a Lustr on `Boost Full` and the Type changes to `S4 26`, the mode
row disappears — **but the value is still in the file, and it still feeds the
photometrics.** A hidden field holding a live value is worse than a wrong field
you can see.

So hiding a row is only safe if **changing the type clears what no longer
applies**, and says so. Not silently: the unit's brightness changes when a mode
is dropped, and that belongs in the same place every other recompute lands.

### ⚠ And an unmatched choice must not just go quiet

`photometrics.py` line 230 already carries the scar:

> a candela with no multiplier for the lamp actually in the fixture is a candela
> nobody can use […] which is exactly how every PAR came out blank

Filtering the dropdown to what has a multiplier prevents *choosing* a dead
combination. It does not help the plots that already contain one — an `S4 5` or
a `PARNel`, which have no lamp factors at all. Those should say **why** the
footcandles are blank, not leave an empty cell.

---

## 2. Three ways this could be built, worst to best

**A. Validate after the fact.** Leave both rows, flag the contradiction. Cheap,
and wrong: it lets a designer enter something meaningless and then scolds them.

**B. Disable the row that does not apply.** Honest and visible, but a panel of
greyed-out rows is noise on every single unit, forever.

**C. Render only what applies, from the server.** Recommended. Nothing to
validate. The list is correct for ColorSource on the day ColorSource is added,
because it is read from the table rather than typed into the browser a second
time.

⚠ **What C costs:** the panel's shape changes as you change Type, and a field
appearing and disappearing under the cursor is its own kind of annoying. Worth
prototyping before committing — it may want the row to stay in place and change
its *label* instead.

---

## 3. ✅ The one thing that could have broken this — checked, and it holds

A **Source 4WRD is an LED, and it is modelled as a lamp** — correctly, because
it screws into the same barrel and keeps the same angles. If it had selectable
output modes, a fixture *could* have both, and "never both" would only be true
because nobody had looked.

**Read it: ETC Source 4WRD II datasheet, page 2.**

> Modes (Footprint) — **1 Channel (Intensity) for DMX**
> Onboard presets — **No**

One mode, no presets. It is a fixed-white engine on an intensity channel, and
there is nothing for a mode dropdown to offer.

⭐ And the reason the three variants are three *lamps* rather than three modes of
one lamp is on page 1: **"For White please add -1 to the Model / Part Number."**
Gallery and Daylight Gallery are **different part numbers you order separately**.
Three products, three lamps, which is what `LAMP_MF` already says.

**So the empty overlap is a fact about the fixtures, not a gap in the data.**
That is what makes it safe to build on.

---

## Open questions for Jerry

1. Should the lamp list carry **all 22 HPLs**, or the handful you actually
   stock? Twenty-two is complete and a nuisance to scroll; four is a guess about
   somebody else's rig.
2. Does **HPL 375** belong in the default list? It is a real lamp with a
   published factor and it is currently unreachable.
3. When the type changes and a mode is dropped, should that be **silent, a
   notice, or a confirm**? The unit's brightness changes either way.
4. Is the **Lamp row the right place for a 4WRD** at all, or should a retrofit
   be its own thing? It is a lamp when you order it and an LED when you use it —
   though §3 argues the Lamp row is exactly right, because ordering is the part
   that differs and the rental order is what gets it wrong.
