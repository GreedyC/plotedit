#!/usr/bin/env python3
"""A real production's show model cannot reach this PUBLIC repo by accident.

    cd server && python3 test_gitignore.py

🔴 WHY. A show model exported from a real job carries the SHOW AND THE VENUE in
its <title>. Three copies of one sat untracked in samples/, web/ and
web/public/ from 15 Oct, and none of them was ignored — one `git add -A` away
from a client's name on GitHub. They were deleted; this is what stops the next
one. .gitignore already says the same thing about .claude/: "ignoring it is the
cheap way to make sure nothing does by accident."

⚠ THE LAST CHECK IS THE ONE THAT MATTERS MOST. A pattern wide enough to catch
every stray is also wide enough to swallow something the repo needs, and git
will not warn — an ignored-but-tracked file keeps working until somebody
re-clones. web/index.html IS the editor and is tracked, which is why `_m.html`
is an exact name rather than anything broader.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<58} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args],
                          capture_output=True, text=True)


if git("rev-parse", "--git-dir").returncode != 0:
    sys.exit("🔴 not a git checkout — this suite cannot test ignore rules here")


def ignored(path):
    """Does git ignore `path`?  Asked with LINUX case rules, always.

    🔴 core.ignoreCase IS TRUE ON macOS AND FALSE ON LINUX, so `*.png` catches
    plan.PNG on the machine these rules get written on and misses it in CI and
    on anybody else's. Testing with the local setting would have passed here
    and failed there — and worse, would have called a real hole closed.
    """
    return git("-c", "core.ignoreCase=false",
               "check-ignore", "-q", path).returncode == 0


print("an exported show model cannot be staged by accident")
for p in ("samples/_m.html", "web/_m.html", "web/public/_m.html",
          "_m.html", "server/_m.html"):
    check(f"{p} is ignored", ignored(p), True)

print()
print("...and the images it carries with it")
# ⚠ The family, not one extension — a venue photograph is as likely to be a
# .png, and a hole half closed looks closed.
for p in ("samples/garden.jpg", "web/garden.jpg", "web/public/garden.jpg",
          "samples/venue.png", "web/stage.jpeg",
          "plan.PNG", "IMG_1234.JPG", "scan.JPEG"):
    check(f"{p} is ignored", ignored(p), True)
check("web/public/ as a whole is ignored", ignored("web/public/anything.txt"), True)

print()
print("and nothing the repo needs was swallowed")
# 🔴 web/index.html is the editor. A rule like *.html or web/* would ignore it
# and git would say nothing, because it is already tracked — the break only
# appears on a fresh clone.
check("web/index.html is NOT ignored", ignored("web/index.html"), False)
check("the sample plots are NOT ignored",
      ignored("samples/demo.plot.json"), False)

# The general form of the same trap, for every file in the repo rather than the
# two above: git lists tracked files that the ignore rules also match.
both = git("ls-files", "-i", "-c", "--exclude-standard").stdout.split()
check("no TRACKED file matches an ignore rule", both, [])

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
