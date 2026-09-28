# Adding a fixture type — an open discussion

**Status: DISCUSSION. Nothing here is decided, and nothing here is built.**
Opened 2026.09.28 at Jerry's request, to be argued about rather than merged.

It covers three questions he put together, and they turn out to be one question
wearing three hats:

1. A better way to describe **the addresses inside an instrument** — shared
   shapes like `RGBI`, plus custom ones where a fixture is strange.
2. Whether a new instrument type could arrive as an **SVG definition**, and how
   **photometric data** would travel with it.
3. **Making it easier to add a type at all.**

The one question underneath: **what is the smallest complete description of a
fixture type, and who is allowed to write one?**

⚠ The merge gate is not in question. **Only maintainers merge to `main`**, and
everything below assumes that stays true. It is also most of the answer to the
security half of question 2.

---

## 1. Address shapes

### What exists now

`server/plotedit/dmx.py` maps a model and a profile to **a number**:

```
"Source Four LED Series 2": {"Direct": 10, "HSIC": 7, "HSI": 6,
                             "RGB": 6, "Studio": 6, "HSI Plus 7": 15}
```

That number is enough for the only thing the app does with it today — work out
that `2/21` on a fifteen-channel profile occupies `2/21-2/35`, and print the
range on the schedule.

**It is not enough for anything else.** It cannot say what address 23 *does*.

### What a shape would add

A shape is the ordered list of what each address controls:

```
SHAPES = {
    "I":    ["intensity"],
    "RGB":  ["red", "green", "blue"],
    "RGBI": ["red", "green", "blue", "intensity"],
    "RGBW": ["red", "green", "blue", "white"],
    "HSI":  ["hue", "saturation", "intensity"],
    "CMY":  ["cyan", "magenta", "yellow"],
}
```

and a profile becomes a shape plus whatever that particular fixture puts around
it:

```
("Source Four LED Series 2", "HSI"): {
    "shape": "HSI", "then": ["strobe", "curve", "fan"], "count": 6,
    "source": "ETC Source Four LED Series 2 datasheet p.11",
}
```

**⭐ Three things fall out of this that are worth having.**

- **Most fixtures stop needing their own data.** An RGBW par from any maker is
  `RGBW`. The shared shapes cover the common cases and the custom ones are then
  genuinely rare, which is the right shape for a contribution standard.
- **It is checkable.** `len(shape) + len(then) == count` is an invariant a test
  can assert for every profile that has a published count. Today nothing checks
  the number at all — the `HSI Plus 7` entry was wrong by two and only the
  datasheet's worked example caught it.
- **It is the thing that could travel.** `docs/NEXT.md` already records that the
  Eos export writes a bare `channel<address` and cannot say which of two LEDs on
  different personalities is which. A count can never fix that. A shape might.

### ⚠ Three ways this goes wrong

- **Real fixtures are not tidy.** Channels interleave control, strobe, curve and
  fan with colour, and the order is the manufacturer's whim. A shape has to allow
  a named gap — an explicit `"unused"` slot — or it will be quietly forced to
  lie. `RGB` and `Studio` on the Series 2 are six-channel profiles *in which
  channel 4 is unused*; that fact has to survive.
- **A shape is a claim, and a wrong claim is worse than no claim.** Same rule as
  the counts: **every shape cites its document, and an unsourced shape is absent
  rather than guessed.** A patch sheet that names what address 23 does looks
  exactly as authoritative whether it is right or wrong.
- **The count stays authoritative.** If a shape disagrees with a published count,
  the shape is wrong. Deriving the count *from* the shape would have turned the
  `HSI Plus 7` mistake into six wrong addresses on paperwork instead of a caught
  test failure.

### ➡ Suggested position

**Write the shape table. Do not put it on screen yet.**

Shapes cost little and make the existing counts testable, which is worth it on
its own. But nothing in the app consumes a shape today, and a field in the
inspector that nothing reads is a promise the export cannot keep. **Build the
consumer first** — an Eos export that can carry a personality, or a patch sheet
that says what each address controls — and let the shape arrive with it.

---

## 2. SVG definitions, and the photometrics that would have to come too

**`docs/DECISIONS.md`, 2026.09.26, refused imported SVG.** That decision answered
a specific question: *can I hand the app a drawing file for a fixture it does not
know?* The three reasons were that an SVG is not a symbol, that a second runtime
source of geometry guarantees drift, and that XML from the internet into a local
server is a real exposure.

**⭐ What Jerry is asking now is a different proposal**, and it deserves its own
argument: not a bare drawing, but **a package** — geometry *and* photometrics
*and* DMX profiles, arriving as one artifact.

### The case for it

- **It matches how the data actually arrives.** A manufacturer publishes a
  datasheet, an IES file and a DMX chart together. A bundle mirrors the shape of
  the source material instead of scattering it across three modules.
- **A non-programmer could produce one.** Today a new fixture means editing
  Python in three places. That is a real barrier and it is the thing Jerry
  actually wants fixed.
- **It is validatable at the boundary.** One artifact means one schema and one
  place to reject a bad contribution — which is easier to be strict about than
  three hand-edited tables.
- **It could ship without a release.** A house with an unusual inventory could
  carry its own bundles.

### The case against

- **The one-place rule still holds.** `symbols.py` feeds both the PDF and the
  browser through `GET /symbols`, precisely so screen and paper cannot drift.
  Geometry arriving by a second route is that mistake wearing a different hat,
  and `test_agreement.py` exists because it has already happened once.
- **The XML exposure is unchanged.** Entity expansion, external references,
  embedded script. Bundling does not make the parser safer.
- **Photometrics have a provenance standard that a drive-by file cannot meet.**
  Every figure names its source. A bundle from a stranger arrives with whatever
  its author typed, and *"corroborated by the model name"* is not the same class
  of evidence as a datasheet page number.
- **Plots would gain an external dependency.** If a plot references a bundle,
  opening it on another machine needs that bundle. Today a plot is one JSON file
  that stands alone, which is most of why the format is pleasant.

### 🔴 The observation that may settle it

Work out what the bundle must carry for the symbol to be correct:

| Needed | Does an SVG have it? |
|---|---|
| Real size in feet | no |
| Origin at the yoke — what it rotates about | no |
| Facing | no |
| Line weights from the three RP-2 §6.18 allows | no — pixel strokes |
| Beam designation as part of the symbol (§2.2) | no |
| Photometrics with a cited source | no |
| DMX profiles with a cited source | no |

**Every hard thing is metadata, and the SVG supplies only path data.** Once the
schema demands all seven, the drawing file is maybe a tenth of the artifact and
the other nine tenths is a form.

Which reframes the question. It was never *SVG or code*. It is **can a fixture
type be data rather than code** — and if the answer is yes, the format should be
chosen on its merits, not because SVG is what a drawing program exports.

### 🔴 And the format may already exist: GDTF

**Raised 2026.09.28** by the developer of another plot application, in a
conversation about where the two might interoperate. He was explaining why he
would not want to duplicate fixture and DMX logic between projects: **his
application treats GDTF and MVR as its canonical source** for fixture and scene
data.

**⭐ GDTF is the bundle this document was speculating about.** It is an industry
format — a zip carrying a description of the fixture, its geometry, its DMX
modes and its photometrics — and it is published by manufacturers rather than
written by whoever wants the fixture drawn.

Which answers two of the three questions above at once:

- **The bundle format does not need inventing.** Section 2 asks whether a fixture
  type could arrive as a package. One already does.
- **Channel functions are the address shapes.** Section 1 proposes `RGBI` and
  friends as reusable layouts. **A GDTF DMX mode describes exactly that**,
  per channel, from the maker rather than from our reading of a datasheet.

⚠ **It does not settle it, and the seven-row table above still applies.** GDTF is
heavy, it is XML in a zip, and reading one is a real dependency rather than an
afternoon. The line weights, the yoke origin and the RP-2 beam designation are
still ours to decide, because GDTF describes a fixture and not a plot symbol. And
a GDTF's photometrics come with the maker's word rather than a page number, which
is not the same standard as `FIXTURES` holds itself to today.

**➡ But it changes the question.** Not *"should we design a format?"* but
*"should we read the one the rest of the industry already publishes?"* — which is
a better question, and it arrived from someone with no stake in the answer.

**❓ What to find out before deciding:**

- **How much of a GDTF is actually usable** without trusting it. Which figures
  carry a source, and which are the maker's assertion.
- **Whether the fixtures Jerry works with have GDTF files at all.** ETC do. A
  SHEHDS 350W from a marketplace may not, and it is exactly the awkward fixture
  that made `dmx.py` necessary.
- **Whether reading GDTF makes the symbol problem better or worse.** A file that
  answers the DMX question but not the drawing question may leave the hard half
  exactly where it is.

---

## 3. Making it easier, in the order the steps actually pay

**A ladder, cheapest first. Each rung is useful alone.**

1. **The alias route, which already exists.** Mapping an unrecognised name onto
   an RP-2 family in `fixture_names.py` is one line and no geometry. Most people
   asking for a custom symbol want their unfamiliar unit to stop being a blank.
   `CONTRIBUTING.md` offers this first, and it should keep doing so.
2. **A scaffold.** `python new_fixture.py "Maker Model 26"` writes the stub in
   every place a fixture type has to appear, with the required fields present and
   empty and a comment saying what each one needs. Adding a type becomes filling
   in a form, without inventing a file format.
3. **A validator in CI.** Geometry present, yoke at the origin, line weights
   legal, photometrics cited, DMX shape summing to its published count. **This is
   the rung that makes contributions safe to accept**, and it is worth more than
   any file format.
4. **Only then**, if 2 and 3 are not enough, a bundle format — designed against
   the seven-row table above, and parsed by something other than a general XML
   reader.

⭐ **Steps 2 and 3 need no decision about SVG at all.** They are worth doing
whatever the answer to question 2 turns out to be, which is a good sign that they
are the real work.

---

## What the merge gate does and does not solve

**Only maintainers merge to `main`.** That is the answer to *"can a stranger put
a bad fixture in the release?"* — no, review is the gate, and a validator makes
review mechanical rather than a matter of care and attention.

⚠ **It is not the answer to the XML exposure.** That one is about a file a user
feeds their own local server, which never goes near a pull request. Review
protects everyone else's release; it does not protect the person who downloaded
a bundle from a forum.

---

## Open questions for Jerry

- **Is there a real second fixture** whose profiles are documented well enough to
  test a shape table against? One example proves a format; one example is also
  how the `HSI Plus 7` arithmetic went wrong.
- **Would a house ever need a private fixture** that never goes upstream? That is
  the strongest argument for data over code, and it has not come up yet.
- **Which consumer comes first** — the Eos export carrying a personality, or a
  patch sheet that says what each address does? The shape table should be built
  to serve whichever it is.
- **Is a shape table worth writing at all if GDTF is read later?** Possibly yes —
  a shape is small, it makes today's counts testable, and it is what a GDTF DMX
  mode would be read *into*. But it should be designed as a target for that, not
  as a rival to it.
