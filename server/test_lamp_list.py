#!/usr/bin/env python3
"""The lamp dropdown and LAMP_MF must offer the same lamps.

    cd server && python3 test_lamp_list.py

The list the browser shows is a SECOND COPY, typed by hand in web/src/main.ts,
of the keys in photometrics.LAMP_MF. Nothing kept the two in step, and they
drifted twice:

  · The three Source 4WRD retrofit burners gained multipliers in v0.1.19 and
    were never added to the dropdown. For a whole release the app could compute
    a 4WRD and gave nobody a way to choose one.
  · HPL 375 and HPL 550/77 had no multipliers at all until 2026.09.29, so two
    real lamps — one of them the dimmer doubling burner — could not be recorded.

Neither was caught by a test, because every test asked Python and no test ever
read the browser's list. This one does. It is a stopgap: the real fix is for the
server to answer which lamps apply, the way it already answers `fixtures`, which
is argued in docs/LAMP-AND-MODE.md. Until that lands, this fails loudly the day
somebody adds a lamp to one side and forgets the other.
"""
import os
import re
import sys

from plotedit import photometrics as ph

MAIN_TS = os.path.join(os.path.dirname(__file__), "..", "web", "src", "main.ts")

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


src = open(MAIN_TS, encoding="utf-8").read()

# ⚠ The array spans several lines, so DOTALL — and it is matched non-greedily so
# a later `]` in the file cannot swallow the rest of the deps object.
m = re.search(r"\blamps:\s*\[(.*?)\]", src, re.DOTALL)
if m is None:
    print("FAIL  could not find the `lamps:` array in web/src/main.ts")
    sys.exit(1)

in_browser = set(re.findall(r'"([^"]+)"', m.group(1)))
in_python = set(ph.LAMP_MF)

print("every lamp the browser offers has a multiplier table")
check("lamps in main.ts", len(in_browser), len(in_python))
check("offered but unknown to LAMP_MF", sorted(in_browser - in_python), [])
check("in LAMP_MF but not offered", sorted(in_python - in_browser), [])

print("\nthe ones that drifted before are present on both sides")
for lamp in ["Source 4WRD II", "Source 4WRD II Gallery",
             "Source 4WRD II Daylight Gallery", "HPL 375", "HPL 550/77"]:
    check(f"{lamp!r}", (lamp in in_browser, lamp in in_python), (True, True))

# ⭐ Offering a lamp is not the same as it being USABLE. A lamp with an empty
# table would pass everything above and compute nothing on every fixture.
print("\nand each one actually multiplies something")
for lamp in sorted(in_python):
    check(f"{lamp!r} covers fixtures", bool(ph.LAMP_MF[lamp]), True)

print()
if FAILS:
    for f in FAILS:
        print("FAILED:", f)
    sys.exit(1)
print("all passed")
