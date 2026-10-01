#!/usr/bin/env python3
"""Refuse to publish a release note that Markdown will quietly eat.

    cd server && python3 check_release_notes.py ../notes.md
    git tag -l --format='%(contents)' v0.1.26 | python3 check_release_notes.py -

A git tag message is PLAIN TEXT. A GitHub release body is MARKDOWN. release.yml
copies the first straight into the second, so any character that means something
to Markdown stops meaning what it said.

🔴 IT HAS ALREADY HAPPENED, IN PUBLIC. v0.1.26's note explained a piece of dead
code with:

    its old dropdown handler was left behind — a <button> never fires that event

GitHub allows a fixed list of HTML tags and deletes the rest, so that sentence
reached the release page as "a  never fires that event" — subject removed, and
nothing on the page to show a word was missing. It sat there from 05:45 until it
was found by rendering the note before posting it rather than after.

⭐ WHAT THIS CHECKS WAS MEASURED, NOT GUESSED. Every construct below went
through GitHub's own /markdown endpoint on 2026.10.01 and the output was
compared with the input, word by word:

    a <button> never fires          →  "a  never fires"         ⚠ word gone
    a <b>bold</b> tag               →  "a bold tag"             ⚠ tags gone
    an <!-- comment --> hides this  →  "an  hides this"         🔴 whole span gone
    an autolink <https://x/y>       →  unchanged                ✅ allowed
    the call set_layer_ui_config    →  unchanged                ✅ intraword _
    the flags _fit_ and _scale_     →  "the flags fit and"      ⚠ underscores gone
    a glob test_*.py and web/*.ts   →  "test_.py and web/.ts"   ⚠ asterisks gone
    one glob test_*.py on its own   →  unchanged                ✅ nothing to pair

🔴 THE GLOB IS THE ONE THAT WILL CATCH SOMEBODY OUT, and it is why this counts
by PARAGRAPH rather than by line. Both halves were measured:

    a glob test_*.py here
    and another web/*.ts on the next line   →  "test_.py … web/.ts"  ⚠ BOTH eaten
    a glob test_*.py alone in its paragraph →  unchanged             ✅ fine
    and web/*.ts alone in a LATER paragraph →  unchanged             ✅ fine

⭐ So emphasis pairs across the lines of one paragraph and stops at the blank
line. A line-by-line check gets this exactly backwards: it would shout about the
single glob everybody writes, and say nothing about the pair that actually
breaks. A guard that cries wolf is a guard somebody switches off.

🔴 THIS IS A FLOOR, NOT A CEILING. It knows about the constructs above and
nothing else. The exhaustive check is to render the note through /markdown and
compare the words out against the words in, which is how the table above was
produced; reach for that if something still slips through. It is deliberately
NOT done here, because a release that cannot be cut while an API is unreachable
is a worse problem than the one being solved.

The fix, in every case, is to wrap the thing in backticks — which reads better
in the tag message too.
"""
import re
import sys

# A tag, a closing tag, or an HTML comment. `<!--` first so it is not read as a
# tag named "!".
TAGLIKE = re.compile(r"<(?:!--|[!/]?[A-Za-z])[^>\n]*>")
# ⭐ `<https://…>` and `<mailto:…>` are real Markdown and render as written, so
# they are allowed through rather than nagged about.
AUTOLINK = re.compile(r"^<[A-Za-z][A-Za-z0-9+.-]*:[^>\s]*>$")

# ⭐ `*` and `_` are NOT symmetrical, which is the whole reason there are two
# rules here rather than one. `*` works inside a word, so any two of them in a
# paragraph can pair; `_` cannot open inside a word, so `test_*.py` keeps its
# underscore and loses its asterisk — measured, not assumed.
USABLE_STAR = re.compile(r"(?<=\S)\*|\*(?=\S)")
LEFT_US = re.compile(r"(?<![0-9A-Za-z_])_(?=[^\s_])")
RIGHT_US = re.compile(r"(?<=[^\s_])_(?![0-9A-Za-z_])")

# A blank line ends a paragraph, and a list marker starts a new one — emphasis
# does not reach from one bullet into the next.
BULLET = re.compile(r"^\s*(?:[-*+·•]\s|\d+[.)]\s)")

FENCE = re.compile(r"^\s*```")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")


def mask_code(text):
    """Blank out code, keeping every line the same length so numbers hold.

    ⚠ Inline spans are matched per line. Markdown allows one to straddle a line
    break; no tag message has ever done it, and a span that wrapped would be
    reported rather than missed, which is the safe direction to be wrong in.
    """
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
        elif in_fence:
            out.append(" " * len(line))
        else:
            out.append(CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line))
    return out


def paragraphs(lines):
    """[(first line number, text)] — the unit Markdown actually pairs within."""
    out, cur, start = [], [], 1
    for n, line in enumerate(lines, start=1):
        ends = not line.strip() or BULLET.match(line)
        if ends and cur:
            out.append((start, "\n".join(cur)))
            cur = []
        if not line.strip():
            continue
        if not cur:
            start = n
        cur.append(line)
    if cur:
        out.append((start, "\n".join(cur)))
    return out


def problems(text):
    """[(line number, what, the offending bit)] — empty means safe to publish."""
    found = []
    masked = mask_code(text)
    raw = text.splitlines()

    for n, line in enumerate(masked, start=1):
        for m in TAGLIKE.finditer(line):
            if not AUTOLINK.match(m.group(0)):
                found.append((n, "HTML is stripped, taking its text with it",
                              m.group(0)))

    # ⚠ Counted per paragraph, because that is the span emphasis pairs across.
    # One asterisk has nothing to pair with and renders as written; two anywhere
    # in the same paragraph take each other out, even on different lines.
    for start, para in paragraphs(masked):
        stars = USABLE_STAR.findall(para)
        if len(stars) >= 2:
            found.append((start, f"{len(stars)} * in one paragraph pair into "
                                 "emphasis and vanish", para.strip().split("\n")[0]))
        if LEFT_US.search(para) and RIGHT_US.search(para):
            found.append((start, "_ pairs into emphasis and vanishes",
                          para.strip().split("\n")[0]))

    found.sort(key=lambda p: p[0])
    # The excerpt for a tag is the tag; for a paragraph, show the real source
    # line rather than the masked one.
    return [(n, why, what if what.startswith("<") else raw[n - 1].strip())
            for n, why, what in found]


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: check_release_notes.py <file|->")
        return 2
    text = sys.stdin.read() if argv[1] == "-" else open(
        argv[1], encoding="utf-8").read()

    found = problems(text)
    if not found:
        print(f"release notes are safe to publish as Markdown "
              f"({len(text)} characters, {len(text.splitlines())} lines)")
        return 0

    # 🔴 The message has to say the FIX, not just the fault. Whoever sees this is
    # mid-release with a tag already pushed.
    print("::error::the release note contains Markdown that would be eaten:")
    for n, why, what in found:
        print(f"  line {n}: {why}")
        print(f"           {what}")
    print()
    print("Wrap each one in backticks. The tag is already pushed, so:")
    print("  git tag -f -a <tag>        # edit the message")
    print("  git push --force origin <tag>")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
