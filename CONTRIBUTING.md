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

```
cd server && ../.venv/bin/python -m pytest
cd web && npm run test:all      # npm test alone runs only the geometry suite
```

**A test that passes when the code is broken is worse than no test.** Before you
believe a new test, break the thing it covers on purpose and watch it fail. This
has caught more bad tests in this repo than review has.

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
