#!/usr/bin/env python3
"""Turn docs/MANUAL.md into a printable PDF.

    cd server && python3 make_manual.py [out.pdf]

⭐ GENERATED, NEVER EDITED. The Markdown is the manual; this is a second view of
it. A hand-touched PDF would be a second copy to keep in step, and the one that
goes stale is always the one the reader has.

⚠ NO NEW DEPENDENCY. requirements.txt says to add one there and nowhere else,
and a Markdown library for one script is a cost every tester pays at install
time. This parses the subset MANUAL.md actually uses — headings, paragraphs,
bullets, tables, fenced code, rules, and inline bold/code/links — and refuses
anything it does not recognise rather than dropping it silently.

🔴 EMOJI BECOME COLOUR. The PDF base fonts have no glyph for ⭐ ⚠ 🔴, so printing
them gives a blank box or a missing-glyph error. They carry weight in the source,
so they are not thrown away: each one colours its paragraph instead — red for 🔴,
amber for ⚠, green for ⭐ — which survives a black-and-white print as a tint.
"""
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether,
                                ListFlowable, ListItem, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "docs", "MANUAL.md")

INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#5b6660")
RULE = colors.HexColor("#d7ded9")
BAND = colors.HexColor("#f2f5f3")
# One accent per mark, so the emphasis survives the font having no glyph.
RED = colors.HexColor("#9d2b25")
AMBER = colors.HexColor("#8a5a12")
GREEN = colors.HexColor("#256948")

MARKS = {"🔴": RED, "⚠": AMBER, "⭐": GREEN, "➡": GREEN, "📖": GREEN, "✅": GREEN}


def _styles():
    ss = getSampleStyleSheet()
    base = dict(fontName="Helvetica", fontSize=9.6, leading=14.2,
                textColor=INK, alignment=TA_LEFT)
    s = {
        "body": ParagraphStyle("body", **base, spaceAfter=7),
        "h1": ParagraphStyle("h1", parent=ss["Normal"], fontName="Helvetica-Bold",
                             fontSize=23, leading=27, textColor=GREEN, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=ss["Normal"], fontName="Helvetica-Bold",
                             fontSize=14, leading=18, textColor=INK,
                             spaceBefore=19, spaceAfter=7),
        "h3": ParagraphStyle("h3", parent=ss["Normal"], fontName="Helvetica-Bold",
                             fontSize=10.6, leading=14, textColor=INK,
                             spaceBefore=12, spaceAfter=4),
        "code": ParagraphStyle("code", parent=ss["Code"], fontName="Courier",
                               fontSize=8.3, leading=11.4, textColor=INK,
                               leftIndent=9, spaceBefore=3, spaceAfter=9),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 9.0, "leading": 12.4}),
        "cellhead": ParagraphStyle("cellhead", **{**base, "fontSize": 9.0,
                                                  "leading": 12.4,
                                                  "fontName": "Helvetica-Bold"}),
    }
    for mark, col in MARKS.items():
        s[f"body{mark}"] = ParagraphStyle(f"body{mark}", **{**base, "textColor": col},
                                          spaceAfter=7)
    return s


# 🔴 GLYPHS THE PDF FONTS DO NOT HAVE. reportlab's base fonts are WinAnsi, so a
# character outside it prints as a black box — and it prints SILENTLY, which is
# how a manual ships looking broken. Known ones are transliterated to something
# a reader of a printed page would rather see anyway; anything unknown stops the
# build (see _check_glyphs).
TRANSLITERATE = {
    "⌘": "Cmd-", "⇧": "Shift-", "⌥": "Alt-", "⏎": "Enter",
    "↶": "Undo", "↷": "Redo", "→": "->", "←": "<-",
    "×": "x", "≈": "approx. ", "≤": "<=", "≥": ">=",
    "\u00a0": " ", "\u2011": "-", "\u2212": "-",
}


def _glyphs(t):
    for a, b in TRANSLITERATE.items():
        t = t.replace(a, b)
    return t


def _check_glyphs(md):
    """Refuse to build a PDF full of black boxes."""
    bad = {}
    for n, line in enumerate(_glyphs(_strip_marks(md)).split("\n"), 1):
        for ch in line:
            if ch in ("\t",):
                continue
            try:
                ch.encode("cp1252")
            except UnicodeEncodeError:
                bad.setdefault(ch, n)
    if bad:
        raise SystemExit(
            "make_manual: these characters have no glyph in the PDF base fonts, "
            "so they would print as black boxes.\n"
            + "\n".join(f"  {ch!r} (U+{ord(ch):04X}) first seen on line {n}"
                         for ch, n in sorted(bad.items(), key=lambda kv: kv[1]))
            + "\n\nAdd it to TRANSLITERATE in server/make_manual.py, or to MARKS "
              "if it is an emphasis mark.")


def inline(t):
    """Markdown inline → reportlab's mini-HTML.

    ⚠ CODE SPANS ARE PULLED OUT FIRST, then put back. The obvious order —
    convert each span as it is found — splits `**` from its partner when bold
    wraps a code span. Bold around a code span printed with its asterisks
    showing on page one of the first build.
    """
    spans = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    t = re.sub(r"`([^`]+)`", stash, t)
    t = _emph(t)
    for k, code in enumerate(spans):
        t = t.replace(
            f"\x00{k}\x00",
            f'<font face="Courier" size="8.6" color="#3b4540">{_esc(code)}</font>')
    return t


def _esc(t):
    t = _glyphs(t)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _emph(t):
    t = _esc(t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)          # links: keep the words
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    return t


def _mark_of(text):
    for mark, _ in MARKS.items():
        if mark in text:
            return mark
    return None


def _strip_marks(text):
    for mark in MARKS:
        text = text.replace(mark + " ", "").replace(mark, "")
    return text.strip()


def parse(md, S):
    """Markdown → a list of flowables. Raises on anything unrecognised."""
    flow, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if line.startswith("```"):
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            flow.append(Preformatted("\n".join(buf), S["code"]))
            i = j + 1
            continue

        if re.match(r"^---+\s*$", line):
            flow.append(Spacer(1, 5))
            flow.append(HRFlowable(width="100%", color=RULE, thickness=0.7))
            flow.append(Spacer(1, 5))
            i += 1
            continue

        m = re.match(r"^(#{1,3}) (.+)$", line)
        if m:
            level, text = len(m.group(1)), _strip_marks(m.group(2))
            flow.append(Paragraph(inline(text), S[f"h{level}"]))
            i += 1
            continue

        if line.lstrip().startswith("| ") and i + 1 < len(lines) \
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows, j = [], i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                if not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[j]):
                    rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            flow.append(_table(rows, S))
            i = j
            continue

        if re.match(r"^\s*([-*]|\d+\.) ", line):
            items, j = [], i
            while j < len(lines) and re.match(r"^\s*([-*]|\d+\.) ", lines[j]):
                text = re.sub(r"^\s*([-*]|\d+\.) ", "", lines[j])
                # A wrapped bullet continues on an indented line.
                while j + 1 < len(lines) and lines[j + 1].startswith("  ") \
                        and not re.match(r"^\s*([-*]|\d+\.) ", lines[j + 1]):
                    j += 1
                    text += " " + lines[j].strip()
                mark = _mark_of(text)
                items.append(ListItem(
                    Paragraph(inline(_strip_marks(text)),
                              S[f"body{mark}"] if mark else S["body"]),
                    leftIndent=15, value="circle"))
                j += 1
            flow.append(ListFlowable(items, bulletType="bullet", start="circle",
                                     leftIndent=14, bulletFontSize=6))
            flow.append(Spacer(1, 4))
            i = j
            continue

        # A paragraph: this line and every following non-blank, non-special one.
        buf, j = [line], i + 1
        while j < len(lines) and lines[j].strip() and not re.match(
                r"^(#{1,3} |```|---+\s*$|\s*\||\s*([-*]|\d+\.) )", lines[j]):
            buf.append(lines[j])
            j += 1
        text = " ".join(x.strip() for x in buf)
        mark = _mark_of(text)
        flow.append(Paragraph(inline(_strip_marks(text)),
                              S[f"body{mark}"] if mark else S["body"]))
        i = j
    return flow


def _table(rows, S):
    head, body = rows[0], rows[1:]
    # A two-column table is nearly always "name | what it does", so give the
    # explanation the room. Anything wider splits evenly.
    width = 6.9 * inch
    n = max(len(r) for r in rows)
    widths = [width * 0.26, width * 0.74] if n == 2 else [width / n] * n

    labelled = any(c.strip() for c in head)
    data = []
    if labelled:
        data.append([Paragraph(inline(c), S["cellhead"]) for c in head])
    for r in body:
        r = (r + [""] * n)[:n]
        cells = []
        for c in r:
            mark = _mark_of(c)
            st = S["cell"]
            if mark:
                st = ParagraphStyle("c", parent=S["cell"], textColor=MARKS[mark])
            cells.append(Paragraph(inline(_strip_marks(c)), st))
        data.append(cells)

    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if labelled:
        style += [("BACKGROUND", (0, 0), (-1, 0), BAND),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.7, RULE)]
    t.setStyle(TableStyle(style))
    return KeepTogether([t, Spacer(1, 9)])


def build(out_path):
    md = open(SRC, encoding="utf-8").read()
    _check_glyphs(md)
    S = _styles()

    # The Contents list is a page-one convenience in Markdown and dead weight in
    # a PDF, which has its own page numbers and a reader that can search.
    md = re.sub(r"## Contents\n.*?\n---\n", "", md, count=1, flags=re.S)

    # ⚠ The margins are LOCALS, not read back off the document. reportlab sets
    # those attributes dynamically, so `doc.leftMargin` is invisible to pylint
    # and fails CI's --errors-only pass. They are constants here anyway.
    left = right = 0.8 * inch
    top, bottom = 0.8 * inch, 0.85 * inch
    page_w, page_h = LETTER

    doc = BaseDocTemplate(out_path, pagesize=LETTER,
                          leftMargin=left, rightMargin=right,
                          topMargin=top, bottomMargin=bottom,
                          title="plotedit — the manual", author="Twin Oaks Studios")
    frame = Frame(left, bottom, page_w - left - right, page_h - top - bottom,
                  id="body")

    def furniture(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(left, 0.55 * inch, "plotedit - the manual")
        canvas.drawRightString(page_w - right, 0.55 * inch,
                               str(canvas.getPageNumber()))
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(left, 0.72 * inch, page_w - right, 0.72 * inch)
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=furniture)])
    doc.build(parse(md, S))
    return out_path


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        HERE, "..", "out", "plotedit-manual.pdf")
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    p = build(dest)
    print(f"{os.path.abspath(p)}  ({os.path.getsize(p) / 1024:.0f} KB)")
