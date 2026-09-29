# Which fields cannot both be true

**Status: PARTLY BUILT, 2026.09.29.** Jerry answered questions 1 and 2 the day
this was written and the inspector now greys the rows out — see
`DECISIONS.md`, "Fields that do not apply go inert, not hidden". §1.3's gap
is closed too: a Source Four's personality dropdown offers `Dimmer` in a
dimmer-is-address house. **What is still only argued here is §5's first two
steps** — the server saying which fields apply, rather than the browser
working it out from tables it happens to have. Written 2026.09.29 at Jerry's
request, after he put the rule plainly:

> if there is an LED then there is no Lamp. A Lustr means it is an LED so having
> an HPL 575 makes no sense. I think we can add the 4WRD as a lamp because it is
> basically serving the same purpose and goes into a standard S4.

That is the rule. This document works out **how far it reaches** — because
lamp-versus-mode is not the only pair in the panel that cannot both be true, and
the others are worth finding before anything is built for the first one.

Companion to `LAMP-AND-MODE.md`, which argues the *mechanism*: let the server say
which fields apply and render only those. This one is the *inventory*.

---

## 0. The evidence, in one table

Cross-tabulating every fixture in `FIXTURES` against `LAMP_MF`, its own `modes`,
and `dmx.FAMILY_MODELS`:

| Family | Lamp | LED mode | Model / personality |
|---|---|---|---|
| S4, S4 EDLT, S4 PAR | ✅ | — | — |
| S4 Zoom, PARNel | — | — | — |
| Lustr | — | ✅ | ✅ |
| ColorSource, ColorSource Zoom, ColorSource CYC | — | ✅ | ✅ |
| Cyc (Altman Spectra) | — | — | ✅ |
| SHEHDS | — | — | — |

**The lamp column and the mode column never both tick.** Not once, across 47
fixtures. And the model column follows the mode column almost exactly, which is
the real shape of the thing: **the panel is two panels wearing one coat.**

---

## 1. The pairs, and what each one rests on

### 1.1 🔴 Lamp ↔ LED mode — the one Jerry raised

**A fixture has a lamp or an output mode, never both.** A barrel with an HPL in
it has no menu to set; an LED engine has no lamp to order.

This is not an inference from naming. `LAMP_MF` is keyed by fixture and so is
`FIXTURES[k]["modes"]`, and **the two key sets do not intersect**.

⚠ **It is currently expressible and currently wrong in the sample data.**
`plots/sample.plot.json` has `GRID D` unit 1 as a `Lustr 26 EDLT` carrying
`lamp: "HPL 575"`. The app accepts it, stores it, and ignores it — the Lustr's
output comes from its mode. **A field that accepts a value and does nothing with
it is worse than a missing field**, because the designer believes they have said
something.

### 1.2 ✅ Dimmer ↔ Address — already decided, already enforced

This pair is **settled and working**, and is the model for how the rest should
go. From `dmx.plot_number`:

> Jerry, 2026.09.28: "hexagon carries dimmer or address." […] a unit on a circuit
> for power and an address for control is two facts about two different things

`patch_cell` and `plot_number` both let **the address win** if a unit somehow has
both, and the docstring says why: *"a unit should never have both, but if the
data says otherwise the two functions must not disagree."*

⭐ **Note what was done there and not done for lamp/mode:** the exclusion was
enforced at the point of *reading*, consistently, in one place, with the
tie-break written down. Nobody hid a field. That is a cheaper pattern than
hiding rows, and it may be the right one here too.

### 1.3 Model and DMX personality ↔ a tungsten fixture

`FAMILY_MODELS` offers models for **Lustr, ColorSource ×3, and Cyc** — every one
an LED — and for **no** S4 family. So on a tungsten S4 both dropdowns render
empty and can never be filled.

That is the same bug as the mode row, one field over. It is less visible only
because an empty dropdown looks like missing data rather than a contradiction.

### 1.4 Lens angle ↔ anything that is not an oval-beam unit

`symbols.for_type` passes `lens_rotation` to exactly one shape,
`oval_beam_fresnel`, reached only when the type matches `parnel` or `oval`.
**On every other fixture the value is accepted and silently discarded.**

The field's own hint already says "Oval-beam units (PARNel)" — so the app knows
the rule and writes it in prose to the user instead of acting on it.

---

## 2. ⭐ The 4WRD is the deliberate exception, and it is right

Jerry: *"we can add the 4WRD as a lamp because it is basically serving the same
purpose and goes into a standard S4."*

Agreed, and the reasons are worth recording because this is the one place the
tidy rule is broken on purpose:

- **It goes in the barrel.** Same tube, same lens, same angles. The thing you
  hang is a Source Four.
- **It is a thing you order.** Three separate ETC part numbers — the datasheet's
  *"For White please add -1 to the Model / Part Number"* — not three settings.
  The rental order and the shop both treat it as a lamp.
- **The photometrics key off the lamp**, and its multipliers sit in `LAMP_MF`
  beside the HPLs because that is arithmetically what they are.
- **It has nothing a mode field would hold.** Datasheet p2: *"Modes (Footprint):
  1 Channel (Intensity) for DMX"*, *"Onboard presets: No"*.

So a retrofitted S4 is **an LED with a lamp and no mode**, and the rule in §1.1
survives — because the rule is really *"lamp or mode, never both"*, not *"LEDs
have modes."*

### ✅ And the patch already gets it right, by a fallback that happens to be true

A retrofitted S4 is on a DMX address, not a dimmer. Its family has no models, so
no personality can be chosen. Asked anyway:

```
patch_cell(S4 26, address "1/45", no model, no profile)
  → ('1/45', 'address — a conventional fixture is one address', 1)
```

**A footprint of 1, which is exactly right** — the 4WRD is one channel of
intensity. The app reaches the correct answer through a default meant for
something else. ⚠ Worth knowing before somebody "fixes" the default.

---

## 3. What is NOT mutually exclusive, so the list is honest

- **Circuit.** An LED still needs power. It applies to everything, and it is
  never generated because circuits belong to the house.
- **Colour, gobo, accessories.** Paperwork and symbol decoration; nothing in
  photometrics reads them. ⚠ A gobo in a fixture with no gate — a PAR, a cyc — is
  meaningless, but **the app does not model which fixtures have a gate**, so it
  cannot say so. Not a rule we can enforce; possibly one worth the data.
- **X, Y, trim, focus.** Geometry applies to every unit.
- **Purpose, notes.** Always.

**And one field that is not exclusive but is two different things:** `trim` on a
vertical position is a height *on the boom*, and it is written to both fields —
the elevation reads one, the photometrics the other. Already handled; listed here
so nobody counts it as a contradiction.

---

## 4. 🔴 Why there is no beam-angle field — Jerry's pool observation

> changing the Lustr 26 EDLT to a Lustr 36 EDLT changes the size of the pool

Correct, and it is the design rather than a side effect. **The lens is part of
the type**, not a separate field:

| Type | field | beam | pool at an 18 ft throw |
|---|---|---|---|
| `Lustr 26 EDLT` | 27.7° | 25.3° | **8.9 ft across** |
| `Lustr 36 EDLT` | 34.8° | 33.0° | **11.3 ft across** |

`FIXTURES` is keyed per lens tube, and `symbols.for_type` parses the degrees out
of the type name to pick the symbol. So Type carries the optics, and there is no
beam-angle box to contradict it.

⭐ **This is the pattern the rest of the panel should copy.** Nobody can put a 36°
angle on a 26° fixture, because there is no field in which to say it. That is
what §1.1 is asking for, applied to lamp and mode.

---

## 5. What this means to build, smallest first

1. **Say which fields apply, from the server.** `/fixtures` already publishes
   each type's `modes`; it should also publish its lamps and its models, all
   three from the tables that own them. One endpoint, no new data.
2. **Render only what applies.** The contradiction stops being something to
   validate and becomes something that cannot be typed.
3. **🔴 Clear what no longer applies when the type changes** — and say so. This
   is the trap, not the feature. A Lustr on `Boost Full` changed to an `S4 26`
   keeps feeding that mode to the photometrics with the row invisible. **A hidden
   field holding a live value is worse than a wrong field you can see.**
4. **Clean the sample plot**, which currently carries `Lustr 26 EDLT` +
   `HPL 575` and would silently keep it.

⚠ **What §1.2 suggests instead, and is worth weighing:** dimmer/address was
solved *without hiding anything* — one reader, one tie-break, written down. If
hiding rows proves annoying in practice (the panel changing shape under the
cursor), the fallback is to leave both rows and make the reader authoritative.

---

## Open questions for Jerry

1. ✅ **Answered 2026.09.29 — it does not arise.** Nothing is cleared, because
   nothing is hidden. A mode that no longer applies goes grey and keeps its
   value, so there is no silent drop to warn about.

   ⭐ **And the photometrics were already safe, which was checked rather than
   assumed.** A `Lustr 26 EDLT` computes 165.3 fc at 18 ft on `Regulated 3200K`
   whether or not a stray `HPL 575` is attached, and an `S4 26` computes 423.7 fc
   on its HPL whether or not a stray `Boost Full` is attached. **The number that
   does not apply is ignored in both directions.** So a greyed field is inert on
   the screen *and* in the arithmetic; the only trace it leaves is a line in the
   file.
2. ✅ **Answered 2026.09.29: inert.** *"lets try having unused fields greyed-out."*
3. Is a **gate** worth modelling — which fixtures can take a gobo at all? It
   would make the gobo field honest, at the cost of a flag per fixture.
4. The **SHEHDS** has no lamps, no modes and no models: it is under-described
   rather than a counterexample. Does it need a personality table, or is it
   fine as a shape on a plot?
