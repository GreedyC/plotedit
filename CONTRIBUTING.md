# Contributing to plotedit

plotedit draws light plots to **USITT RP-2 (2006)**, *Recommended Practice for
Theatrical Lighting Design Graphics*. That standard is the whole point of the
program: a plot is readable by an electrician who has never met you because the
symbols mean something fixed. Every contribution is measured against it.

Contributions are welcome. The most common one is a **new fixture symbol**, and
that has its own standard below.

---

## Before anything else

- `main` is protected. Work on a branch, open a pull request, and merge once CI
  is green. Required checks: `tests`, `web`, `pylint`.
- Fork, or branch if you have write access. Both are fine.
- The program is GPL-3.0. By contributing you agree your work ships under it.

### Running it

```
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
cd web && npm install && npm run build
cd ../server && ../.venv/bin/python serve.py
```

On Windows, `run.bat` does all of that and is the normal way to run it.

### The tests

The suites are plain scripts, not pytest. CI runs them exactly like this:

```
cd server && for f in test_*.py; do python "$f"; done
cd server && python verify_suites.py
cd web && npx tsc --noEmit && npm run test:all
```

`npm test` on its own runs only the geometry suite; `test:all` is the whole thing.

**A test that passes when the code is broken is worse than no test.** Before you
believe a new test, break the thing it covers on purpose and watch it fail.

This is not just advice here — `verify_suites.py` does it automatically, breaking
each suite and checking it actually goes red and names what broke. It runs in CI.
A suite that passes no matter what you do to the code will fail that check.

---

## Adding a fixture symbol

This is the path for a fixture plotedit does not yet draw. It is deliberately a
code contribution rather than a file you import at runtime, for three reasons:

- The geometry stays in **one place** — `server/plotedit/symbols.py` — so the PDF
  and the browser cannot drift apart. They already draw from the same source via
  `GET /symbols`, and that is not an accident.
- A symbol carries things a drawing file does not: a real-world size in feet, an
  origin at the yoke, a facing, and line weights that survive a change of scale.
- It gets reviewed against the RP-2 plate before it reaches anyone else's plot.

**You are not blocked while you wait.** Add the symbol in your own fork and it
works immediately, on your plots, tonight. The pull request is only how the
fixture reaches everyone else. Nobody has to wait on review to get their show
drafted.


### ⭐ First — check whether you need a symbol at all

**Your fixture almost certainly draws already.** `symbols.for_type` falls back to
a beam angle read out of the name, so an unknown instrument comes out as an ERS
rather than as nothing. What an unrecognised fixture is missing is usually not
the drawing — it is the **photometrics**: no pool, no footcandles, and a note
saying why.

So, in order of effort:

**1. Is it a fixture the table already holds, under another spelling?** Then it
belongs in `ALIASES` in `server/plotedit/fixture_names.py` — that table is *only*
for a fixture that really is the one we hold data for, such as a rebadge or a
Lightwright spelling nobody anticipated.

**⚠ The key is the NORMALISED form, not what the paperwork says.** `normalise()`
strips the manufacturer, unifies Source4/S4, turns `°` into a degree number and
drops punctuation. Run it to find out what to type:

```python
>>> from plotedit.fixture_names import normalise
>>> normalise("Chauvet Ovation E-260WW")
'ovation e 260ww'
```

**2. Is it a real fixture nobody has a datasheet for?** Then it goes in
`NO_DATA`, with the reason — `"lekolite 26": "Strand LekoLite — no datasheet
fetched"`. It is then recognised and named honestly, and it draws, and it simply
has no photometrics.

**🔴 Do NOT point it at a fixture whose numbers you want to borrow.** Mapping a
Chauvet to `S4 26` does not give it ETC's optics; it puts ETC's candela on a
Chauvet, and that figure sizes a beam pool somebody will hang a rig by. A blank
is safe. A borrowed number is not, and it looks exactly as authoritative.

**3. Only then, a new symbol** — and only when the fixture genuinely looks
different on paper: a moving light, a cyc unit, a striplight, something RP-2
draws its own way. A 26° ERS from another maker does not; it is already right.

### Two scripts that do the boring half

**`python server/new_fixture.py "Maker Model 26"`** prints the stub for every
table a fixture type has to appear in, with the required fields present and
empty and a note saying what each one needs. It prints rather than edits, on
purpose: pasting takes ten seconds and leaves you looking at the neighbouring
entries, which is where you will notice that every one of them names a document.

**`python server/validate_fixtures.py`** checks what a reviewer reading a diff
cannot see — that every entry cites a source, that a field angle is not narrower
than its beam, that an alias points at a fixture that still exists, that a DMX
footprint is between 1 and 512, and that a profile is not listed as both
published and unpublished. **It runs in CI**, so an entry pasted in and left
unfinished fails the build instead of shipping as a guess.

⚠ **Neither checks that the symbol is the right shape.** Nothing automatic can.
Draw it on a plot, put it beside the RP-2 plate, and look at it.

### What happens after you open the pull request

Jerry reviews it. There is no rota and no service level — it is one person and a
theatre season, so a quiet week happens. **It does not block you**: your fork
already draws your fixture.

What gets sent back, in rough order of likelihood: a symbol that does not match
its RP-2 plate; a dimension with no source; a line weight written as a number; a
name that Lightwright's spelling will never match. None of those are hard to fix,
and the symbol sheet from step 10 usually settles the first one in one exchange.

### The standard

**1. Write a function in `server/plotedit/symbols.py`** that returns a list of
primitives. Follow the existing families — `fresnel()` is the shortest worth
reading, `enhanced_ers()` the most complete.

**2. Coordinates are in feet.** The origin is the **yoke** — the hanging point,
because that is what the symbol rotates about. `+a` runs toward the back of the
instrument, `-a` toward the front, `c` across. Get the origin wrong and every
focus angle on the plot is quietly wrong with it.

**3. Name the RP-2 section in the docstring**, as the existing families do:

```python
def fresnel(size_in=6):
    """§6.2. Rounded back, straight body, and a lens ring standing proud at the
    front — the ring is what distinguishes a Fresnel from an ERS at a glance."""
```

If the fixture postdates 2006 and RP-2 has no plate for it, derive it from the
nearest family and **say explicitly which, and why**. A reader six months later
needs to know whether a shape is traced from the standard or reasoned from it.

**4. Never write a line weight as a literal.** RP-2 §6.18 gives three and only
three, and they are constants in `scaled_pdf.py`. A hardcoded width does not
survive the jump from 1/4" to 1/2" scale.

**5. Take dimensions from the manufacturer's datasheet, and cite it** with
revision and date — `Rev J 2020-12`, not "the ETC site". Datasheets are revised
and the numbers move. If you measured the real fixture instead, say that.

**6. Register the name in `server/plotedit/fixture_names.py`** so the spellings
that come out of Lightwright and Vectorworks resolve to your symbol. A symbol
that nobody's paperwork matches is a symbol nobody ever sees. There are already
38 distinct names normalising to a much smaller set; add yours to the table.

**7. Photometrics are optional, but must be honest.** If no datasheet was
fetched, say so in the name, as the existing entries do:

```python
"6in fres": "Altman 6\" Fresnel — no datasheet fetched",
```

An invented candela figure will size a beam pool on somebody's plot and they
will hang the rig by it. A blank is safe; a guess is not.

**8. Check that it composes.** `with_accessories()` adds top hats, barn doors and
gobo marks by computing the symbol's extent, and `shade_rear()` blackens the back
for RP-2 §6.15. Both operate on the primitive list. A symbol that breaks either
one is not finished.

**9. Add a test** — that it renders, that its extent is sane for the real
fixture's size, and that the name maps. Then break it on purpose and confirm the
test fails.

**10. Draw the symbol sheet and attach the PDF to the pull request:**

```
cd server && python3 draw_symbol_sheet.py ../out/rp2-symbols.pdf
```

That sheet prints every symbol at twice the size it draws at 1/2" scale, numbered,
with *"MARK UP AND SEND BACK"* across the top. It exists for exactly this review.
A reviewer holding it beside the RP-2 plate can settle in a minute what a
paragraph of description cannot.

---

## Writing style in the codebase

Two conventions worth knowing before your first pull request.

**Comments say why, not what.** The code already says what. The comments in this
repo carry the reasoning that would otherwise be lost — which datasheet, which
standard, what was tried and failed. `⚠` marks a trap someone already fell into.

**Names from conversations do not appear in source.** If someone in a forum
suggested an idea, describe what they wanted — "a designer in the UK" — not who
they are. Asking a question in public is not consent to be a permanent citation
in somebody else's source code.

**Contributors are different.** If you open a pull request you have put your name
on public work by choice, and you get credited for it in `CONTRIBUTORS.md`. Tell
us how you want to appear — full name, handle, or not at all.

---

## Reporting a bug

Say what you did, what happened, and what you expected. Attach the `.plot.json`
if you can — it is plain text and it makes the difference between a fix tonight
and a fix next month.

If something produced a file that was empty or wrong rather than erroring,
say so plainly. Silent wrong output is the worst failure mode this program has,
and it is the one least likely to get reported.
