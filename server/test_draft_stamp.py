#!/usr/bin/env python3
"""A draft stamp is a property of the PRINT, and it is counted by the guard.

    cd server && python3 test_draft_stamp.py

🔴 WHY. A sheet whose title block says Rev L, 2026.10.31 is telling the truth
about the plot it came from and lying about what the sheet is, once that sheet
is a markup print pulled off the same file. Jerry, 2026.11.03, with three
markup sheets about to go on a table beside Monday's printout: "stamp the title
block". The filename is not what a reader reads.

⭐ AN ARGUMENT, NOT A FIELD IN THE PLOT — Jerry's call, 2026.11.03. A plot is
issued and marked up from the same file on the same day, so what the sheet is
belongs to the render, not to the drawing. Nothing is written back.

⚠ AND THE TEXT IS FREE — also his call. MARKUP COPY, PRELIMINARY, NOT FOR
CONSTRUCTION: a studio that prints drafts for different reasons needs different
words, and a fixed list means a code change on the day.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_to_pdf                              # noqa: E402
from plotedit import scaled_pdf as SP           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PLOT = os.path.join(HERE, "testdata", "blackbox.plot.json")
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<60} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def text_of(path):
    import pymupdf
    return "\n".join(p.get_text() for p in pymupdf.open(path))


def render(tmp, **kw):
    out = os.path.join(tmp, "s.pdf")
    sheet, _ = plot_to_pdf.render(PLOT, out, scale="1/4", **kw)
    return sheet, out


import tempfile                                 # noqa: E402

print("the stamp reaches the paper, and only when asked for")
with tempfile.TemporaryDirectory() as tmp:
    _, plain = render(tmp)
    bare = text_of(plain)
with tempfile.TemporaryDirectory() as tmp:
    _, marked = render(tmp, stamp="MARKUP COPY", )
    stamped = text_of(marked)
check("an unstamped sheet says nothing about a markup", "MARKUP COPY" in bare, False)
check("a stamped one does", "MARKUP COPY" in stamped, True)
check("...and says the revision below is the plot's",
      "not this print's" in stamped, True)

print()
print("the words are whatever the print needs")
with tempfile.TemporaryDirectory() as tmp:
    _, p = render(tmp, stamp="NOT FOR CONSTRUCTION")
    check("free text, not a fixed list", "NOT FOR CONSTRUCTION" in text_of(p), True)

print()
print("the date is the PRINT's, not the plot's")
# 🔴 THE WHOLE POINT. blackbox.plot.json carries its own date; the stamp must
# not repeat it, or the stamp inherits the staleness it exists to flag.
import json                                     # noqa: E402
plot_date = json.load(open(PLOT))["date"].replace("-", ".")
with tempfile.TemporaryDirectory() as tmp:
    _, p = render(tmp, stamp="MARKUP COPY")
    t = text_of(p)
    import datetime
    today = datetime.date.today().strftime("%Y.%m.%d")
    check("the stamp carries today", f"Printed {today}" in t, True)
    check("...which is not the plot's date", f"Printed {plot_date}" in t,
          plot_date == today)

print()
print("nothing is hidden without the sheet saying so")
# 🔴 The stamp is opaque and sits ON the title block, so the corner it covers
# grows by STAMP_H. If the guard is not told, a stamped sheet quietly hides a
# strip of drawing — the one failure the block's own warning exists for.
check("STAMP_H is a constant the guard can read before drawing",
      isinstance(SP.STAMP_H, float) and SP.STAMP_H > 0, True)
src = open(os.path.join(HERE, "plotedit", "scaled_pdf.py"), encoding="utf-8").read()
check("the clipping guard measures to the top of the STAMP",
      "if self._tb_low < y0 + tb_h + stamp_h:" in src, True)
check("...and the distance it reports includes it",
      "y0 + tb_h + stamp_h - self._tb_low" in src, True)

print()
print("the fit search draws the sheet that will be ISSUED")
# ⚠ Same rule the pools already follow: searching with a different picture than
# the one issued answers about a different sheet.
pdf_src = open(os.path.join(HERE, "plot_to_pdf.py"), encoding="utf-8").read()
check("the search carries the stamp", pdf_src.count("stamp=stamp"), 3)

print()
print("a character Helvetica cannot set is replaced, not raised on")
with tempfile.TemporaryDirectory() as tmp:
    sheet, p = render(tmp, stamp="MARKUP 中文")
    t = text_of(p)
    check("the sheet still renders", os.path.getsize(p) > 0, True)
    check("...and warns, naming what happened",
          any("STAMP:" in w for w in sheet.warnings), True)

print()
print("the CLI takes it without disturbing the positionals")
check("plot and pdf still land in the right order",
      plot_to_pdf._stamp_arg(["a.json", "b.pdf"]), (["a.json", "b.pdf"], None))
check("--stamp is lifted out from the end",
      plot_to_pdf._stamp_arg(["a.json", "b.pdf", "--stamp", "DRAFT"]),
      (["a.json", "b.pdf"], "DRAFT"))
check("...and from the middle",
      plot_to_pdf._stamp_arg(["a.json", "--stamp", "DRAFT", "b.pdf"]),
      (["a.json", "b.pdf"], "DRAFT"))

print()
print("the section carries it too")
sec = open(os.path.join(HERE, "plot_to_section.py"), encoding="utf-8").read()
check("plot_to_section.render accepts a stamp", "place=None, stamp=None)" in sec, True)
check("...and hands it to the Sheet", "stamp=stamp)" in sec, True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
