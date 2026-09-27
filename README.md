# plotedit

A light plot editor that draws to **USITT RP-2 (2006)** — the symbols, the
notation, the line weights and the section checklist — and computes what the rig
actually does: throws, beam angles, the shape of each pool on the floor, and
footcandles through gel.

It runs entirely on your own machine. Nothing is uploaded anywhere.

**Not a CAD program.** The ground plan comes in as DXF; this never draws
architecture. See [docs/SPEC.md](docs/SPEC.md) for scope and architecture.

## Why it exists

Vectorworks is subscription-only and Lightwright has followed. A designer lighting
ten units on a pipe in a 75-seat room pays a professional-tier subscription to do it.
The tools exist for large productions; nobody serves the small room.

It also fixes a real problem: a `.vwx` file needs a live subscription to open. Two
shows in this designer's own archive are locked inside drawings nothing on the
machine can read. **A plot here is plain JSON** — readable in a text editor, diffable,
and still openable in twenty years.

---

## Running it

**You need Python 3.10 or newer.** Nothing else, if you downloaded a release.

1. Download the latest release and unzip it.
2. Double-click **`run.command`** on a Mac, or **`run.bat`** on Windows.
3. Your browser opens on the editor.

**That is how you start it every time, not just the first.** There is nothing to
install and no separate launcher: the same file sets itself up on the first run
and starts the program on every run after it. The first run takes a minute; after
that it starts in a few seconds.

Leave the terminal window open while you work — closing it, or pressing ctrl-C,
stops the program. If it stops with an error, the window stays open and the
message says why.

> **On Windows**, install Python from
> [python.org](https://www.python.org/downloads/) and tick
> **"Add python.exe to PATH"** in the installer. The `python` that Windows
> offers by default is a Microsoft Store stub that opens the Store instead of
> running anything. SmartScreen may also warn about an unrecognised app —
> **More info** → **Run anyway**.
>
> **Extract the zip before running it.** Windows lets you look inside a zip as
> though it were an ordinary folder, and `run.bat` fails confusingly when it is
> started from in there. Right-click the zip → **Extract All** first.
>
> If it still will not start, the Developing section below works on Windows too,
> one command per terminal.

> **macOS may refuse to open it the first time** — "cannot be opened because it
> is from an unidentified developer". Right-click `run.command` → **Open** →
> **Open**. You only have to do that once. This is macOS being careful about
> anything downloaded from the internet, and it applies to any unsigned program.

Everything it installs goes in a `.venv` folder inside the one you unzipped.
It touches nothing else on your computer, and deleting that folder removes every
trace of it except the plots you saved.

### If you cloned the repository instead

A clone has no built editor in it, so you also need
[Node](https://nodejs.org). `run.command` will build it for you the first time.

---

## Where your plots go

In a `plots` folder next to `run.command`. **Save** writes the file you are
working on; **Save As…** starts a new one; **Open…** lists what is there.

To keep them somewhere else — a show folder, or Dropbox — set `PLOTEDIT_PLOTS`
to that path before starting.

---

## What it does

- **Draws the plot** to RP-2: symbols by fixture family with the beam angle
  marked in the lens, circuit/dimmer/channel in the right containers, accessories
  at the gate or at the nose, and three line weights that mean what the standard
  says they mean.
- **Booms in elevation** (§6.12), beside the plot, compressed with a break mark —
  and the labelled heights stay true, because the break says the paper is short,
  never that a number is approximate.
- **Pools as ellipses**, not circles. A cone only cuts a circle when it points
  straight down; at 30° a 26° field lands more than twice as long as it is wide,
  and the long end is the one that reaches the scenery. Cut them at head height,
  at a face, at seated height, or at the deck.
- **A section** to the RP-2 §3 checklist, which states what it does *not* show
  rather than implying a clearance it has not checked.
- **Exports**: PDF and DXF of the plot, instrument schedule, channel hookup, and
  an Eos patch file.
- **Picks the paper for you.** The sheet defaults to ARCH D landscape at the
  largest standard scale where nothing runs off the edge, and it tells you which
  sheet to move to if a drawing will not fit.

## What it does not do

- **It does not check clearance.** It draws the room and the rig. Masking,
  scenery and rigging points are not in it, so a trim it accepts may still hang
  into a border.
- **It does not invent circuit numbers.** Circuits depend on the house and have
  no set order; it records what the house told you and checks the plot against
  it.
- **The Eos export has never been tested against a console.** It is written to
  the ASCII spec and nothing more. Treat it as a draft.

Every figure it prints names its source, and anything it could not work out says
so instead of being left blank.

---

## Typing measurements

Anywhere it shows a length it also accepts one, in any of these forms:

```
1'6"      1'-6"      1' 6"      18"      1.5
```

Blank means "not known", and the checks say so out loud rather than assuming
zero — a grid height of 0 would be a claim that the ceiling is on the floor.

---

## Layout

```
server/plotedit/   the Python that does the work, plus a FastAPI wrapper
web/src/           the TypeScript front end
symbols/           instrument symbols, drawn to USITT RP-2
samples/           a test ground plan and a test plot
docs/SPEC.md       scope, architecture, the instrument record, v1 vs later
```

## Developing it

```bash
cd server && python3 -m uvicorn plotedit.api:app --reload    # the API, :8000
cd web && npm install && npm run dev                          # the editor, :5173
```

Tests — all of them should pass before anything is committed:

```bash
cd server && for f in test_*.py; do python3 "$f"; done
cd server && python3 verify_suites.py      # breaks each suite to prove it fails
cd web && npx tsc --noEmit && npm run test:all
```

`verify_suites.py` is worth knowing about: it breaks each test suite on purpose
and requires it to fail *and* name what broke. A suite that passes when the code
is wrong is worse than no suite, and this repo has had two.

### Contributing, and fixtures it does not draw

**[CONTRIBUTING.md](CONTRIBUTING.md) — in the repository, not in the download.**

If plotedit will not draw a fixture you own, that is the place to look. There are
two routes, and the first is usually enough. **An unknown fixture already draws**
— the symbol falls back to a beam angle read from its name — so what is normally
missing is its photometrics, and that is a line in
`server/plotedit/fixture_names.py`. A genuinely different symbol, a moving light
or a cyc unit, is a code contribution, and the standard for drawing one to RP-2
is the longest section of that file.

**Fixtures are not imported as SVG**, and `docs/DECISIONS.md` says why. The short
version: a plot symbol carries a real size in feet, an origin at the yoke, a
facing and one of three permitted line weights, and a drawing file carries none
of them. **A fork is not a wait** — your symbol works on your own plots the
moment you write it; the pull request is only how it reaches everybody else.

---

## Data sources

Photometrics come from ETC's own datasheets; gel transmissions from Rosco's product
pages and the myColor swatch app. **Every fixture row names its source.** Where two
sources disagree — the ETC Europe spread table of 2000 and the modern US datasheets
differ on the 26° and 36° — both are kept and the preferred one is marked.

## Names

Paperwork calls a fixture `ETC Source4 36deg`; the photometric table calls it
`S4 36`. **None of the 38 distinct instrument names in the source archive matched
a table key** — plots imported from Lightwright drew correctly and were silently
unlit, every throw computed and every pool and level blank.

`server/plotedit/fixture_names.py` resolves them: normalise, then explicit
aliases, then a list of real fixtures with no photometrics on file and the reason
why. **81% of the archive resolves**; the remainder say what is missing rather
than returning nothing.

```bash
cd server && python3 test_names.py
```

---

## Licence

**GNU General Public License v3 or later.** The full text is in [LICENSE](LICENSE).

In short: **use it, change it, pass it on** — and anything you build on it stays
free in the same way. That is the point rather than a formality. This exists
because the tools for small rigs went subscription-only, and the licence is what
stops this one going the same way in somebody else's hands.

⚠ **No warranty.** It computes beam angles and levels from published photometric
data and states its sources; it does not know your room. Check the numbers
against something you measured.
