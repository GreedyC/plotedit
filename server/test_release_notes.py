#!/usr/bin/env python3
"""The release-note guard must catch what Markdown eats, and nothing else.

    cd server && python3 test_release_notes.py

Two halves, and the second matters as much as the first. A guard that flags
things that are fine gets switched off, and then it is not a guard — so every
construct a real tag message already contains is asserted to pass.

⭐ THE CASES ARE NOT INVENTED. The ones marked "measured" were put through
GitHub's own /markdown endpoint on 2026.10.01 and the rendered output compared
with the input; the expected verdict here is what that comparison actually
showed. See the table in check_release_notes.py.

⚠ This reads no git tags. The release checkout is shallow and has no tag
objects, so a suite that asked git would pass locally and fail in CI for a
reason that has nothing to do with release notes. The one line that caused the
bug is quoted verbatim instead.
"""
import check_release_notes as g

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<56} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def kinds(text):
    """The set of problem descriptions, so order and line numbers do not bind."""
    return sorted({why for _, why, _ in g.problems(text)})


HTML = "HTML is stripped, taking its text with it"
US = "_ pairs into emphasis and vanishes"


def star(n):
    return f"{n} * in one paragraph pair into emphasis and vanish"

# 🔴 THE LINE THAT ACTUALLY SHIPPED BROKEN, quoted from v0.1.26's tag message.
# It reached the release page as "a  never fires that event".
SHIPPED = ("a button in v0.1.25 its old dropdown handler was left behind — "
           "a <button> never\nfires that event, so the code sat there reading "
           "as live and doing nothing.")

print("the bug this exists for")
check("v0.1.26's line is caught", kinds(SHIPPED), [HTML])
check("backticked, it passes", kinds(SHIPPED.replace("<button>", "`<button>`")), [])

print("\nmeasured — these lose text when rendered, so they must fail")
check("an unknown tag", kinds("a <button> never fires"), [HTML])
check("an allowlisted tag", kinds("a <b>bold</b> tag"), [HTML])
check("a closing tag alone", kinds("ends with </div> here"), [HTML])
check("an HTML comment", kinds("an <!-- comment --> hides this"), [HTML])
check("paired underscores", kinds("the flags _fit_ and _scale_"), [US])
check("a glob, twice over", kinds("a glob test_*.py and web/*.ts"), [star(2)])
check("real emphasis", kinds("this is *emphasised* text"), [star(2)])

print("\nmeasured — these survive rendering, so they must pass")
check("a Markdown autolink", kinds("see <https://twinoaks.studio/plotedit>"), [])
check("a mailto autolink", kinds("write to <mailto:plotedit@twinoaks.studio>"), [])
check("intraword underscores", kinds("the call set_layer_ui_config and get_ocgs"), [])
check("a DMX address", kinds("addresses 1/45 and 2/21 are patched"), [])
check("feet and inches", kinds("the trim is 5'-6\" at 40°"), [])
check("a lone asterisk", kinds("footnote* at the bottom"), [])
check("ONE glob, which everybody writes",
      kinds("the suites run as test_*.py in server"), [])
check("an asterisk between spaces", kinds("the product 2 * 3 is six"), [])
check("an arrow", kinds("the value -> the field, and x < y"), [])

print("\ncode is not scanned, because backticks are the fix")
check("an inline span", kinds("a `<button>` never fires"), [])
check("a glob in a span", kinds("run `test_*.py` in server"), [])
check("double backticks", kinds("a ``<button>`` tag"), [])
check("a fenced block", kinds("text\n```\n<button> and test_*.py\n```\ntext"), [])
# ⚠ A span closing on a later line is reported rather than ignored. That is the
# safe direction — a false alarm costs a minute, a silent deletion is public.
check("a span across lines is NOT trusted",
      kinds("a `<button>\nnever` fires") != [], True)

# 🔴 MEASURED AGAINST GitHub's RENDERER, and the results are not symmetrical.
# Emphasis pairs across the LINES of one paragraph or one bullet, and stops at a
# blank line or the next bullet. Counting per line would shout about the single
# glob everybody writes and stay silent on the pair that actually breaks.
print("\nthe span emphasis reaches across is the paragraph, not the line")
check("two globs, two lines, ONE paragraph",
      kinds("a glob test_*.py here\nand another web/*.ts next."), [star(2)])
check("two globs, two paragraphs",
      kinds("a glob test_*.py here.\n\nand web/*.ts there."), [])
check("two globs, two bullets",
      kinds("- a glob test_*.py here\n- and web/*.ts there"), [])
check("two globs, ONE bullet that wraps",
      kinds("- a glob test_*.py in a bullet\n  wrapping to web/*.ts here"), [star(2)])
check("the paragraph is reported at its first line",
      [n for n, _, _ in g.problems("one\n\ntwo\na *b* c")], [3])

print("\nthe shape of a real note holds together")
REAL = """v0.1.26 — Show & Venue gets out of the way

A small one, and the last item on #56. The panel you fill in once was the first
thing between you and the rig; it now starts collapsed.

- SHOW & VENUE STARTS CLOSED. The room, the venue, the designer and the line
  weights are things you set at the beginning of a show.

⚠ YOU WILL NOT SEE THE CHANGE IF YOU HAVE USED PLOTEDIT BEFORE.

Closes #56.
"""
check("a whole note passes", kinds(REAL), [])
check("line numbers are reported from the source",
      [n for n, _, _ in g.problems("one\ntwo\na <button> here\nfour")], [3])
check("masking keeps the line count",
      len(g.mask_code("a `<button>` b\nc\n")), 2)

print("\nand the exit code is the thing the workflow reads")
check("clean notes exit 0", g.main(["x", "/dev/null"]), 0)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    raise SystemExit(1)
print("all passed")
