#!/usr/bin/env python3
"""How many DMX addresses a fixture occupies, and the range that follows.

    cd server && python3 test_dmx.py
"""
import sys

from fastapi.testclient import TestClient

from plotedit import dmx
from plotedit.api import app

client = TestClient(app)
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        FAILS.append(f"{label}: got {got!r}, wanted {want!r}")


print("the profile table, against the datasheet")
# ETC Source Four LED Series 2 datasheet p.11, read off the plate itself.
for profile, want in [("Direct", 10), ("HSIC", 7), ("HSI", 6),
                      ("RGB", 6), ("Studio", 6)]:
    check(f"Lustr {profile}", dmx.channels("Lustr", profile)[0], want)

# 🔴 NOT 6 + 7. The datasheet works this example itself: HSI with Plus 7 is a
# FIFTEEN channel profile — six HSI channels, a spare at 7, the Plus 7 on/off
# control at 8, and the seven native colours at 9-15. The first draft of the
# table computed 13 from the prose and was wrong by two.
check("Lustr HSI Plus 7 is 15, not 6+7", dmx.channels("Lustr", "HSI Plus 7")[0], 15)

# ⚠ Plus 7 is offered on RGB and HSIC too, but the datasheet publishes no count
# for them, and the arithmetic that looks obvious is what got HSI wrong.
check("RGB Plus 7 exists but is not counted",
      dmx.channels("Lustr", "RGB Plus 7")[0], None)
check("...and says to read it off the fixture",
      "read it off" in dmx.channels("Lustr", "RGB Plus 7")[1], True)

check("an unrecorded profile is not guessed", dmx.channels("Lustr", None)[0], None)
check("...and names the range it could be",
      "6 to 15" in dmx.channels("Lustr", None)[1], True)
check("a profile the fixture lacks is refused",
      dmx.channels("Lustr", "Nonsense")[0], None)
check("a fixture with no table returns none", dmx.channels("S4", "HSI")[0], None)
check("every entry cites a document",
      all(dmx.SOURCES.get(f) for f in dmx.PROFILES), True)

print("\nthe range")
check("universe notation is kept", dmx.span("2/21", 15), "2/21-2/35")
check("a plain address stays plain", dmx.span(45, 15), "45-59")
check("one channel is not a range", dmx.span("2/21", 1), "2/21")
check("no count, no range", dmx.span(45, None), None)
check("it may end exactly on 512", dmx.span(498, 15), "498-512")
# ⚠ A fixture cannot run past the end of a universe. Wrapping into the next one
# would describe addresses that do not exist.
check("it does not run past 512", dmx.span("2/500", 15), None)
check("a note where an address goes is not a range", dmx.span("PENDING", 15), None)

print("\nthe cell the schedule prints")
B = dict(x=0, y=10, trim=20, focus_x=0, focus_y=0, channel=1, unit=1)


def cell(**kw):
    """The patch cell for one instrument.

    ⚠ READ THE BODY DEFENSIVELY. If /compute starts refusing the request — which
    is exactly what a wrong type annotation on the address did — there is no
    "instruments" key, and a test that raises here reports a stack trace instead
    of naming the assertion that broke. Twice now a sabotage has "passed" by
    crashing the suite before it could print a verdict.
    """
    r = client.post("/compute", json={"instruments": [dict(B, **kw)]})
    if r.status_code != 200:
        return f"HTTP {r.status_code}", f"the request was refused: {r.text[:120]}"
    rows = r.json().get("instruments") or [{}]
    return rows[0].get("patch"), rows[0].get("patch_note", "")


check("a recorded profile gives a range",
      cell(type="Lustr 26 EDLT", address="2/21", profile="HSI Plus 7")[0], "2/21-2/35")
check("no profile gives the start address only",
      cell(type="Lustr 26 EDLT", address="2/21")[0], "2/21")
check("...and says why there is no range",
      "not recorded" in cell(type="Lustr 26 EDLT", address="2/21")[1], True)

# ⚠ An LED fixture with no profile table must NOT be called one address.
check("an LED with no table is not called conventional",
      "conventional" in cell(type="SHEHDS 19", address="2/21")[1], False)
# 🔴 An unrecognised type used to fall through to "one address", which would
# quietly call an unknown LED a dimmer.
check("an unknown type is not called conventional",
      "conventional" in cell(type="Chauvet Whatsit", address="1/9")[1], False)
check("...and says the type is unknown",
      "not a fixture this knows" in cell(type="Chauvet Whatsit", address="1/9")[1], True)

check("a conventional fixture is one address",
      cell(type="S4 26", address="45"), ("45", "address — a conventional fixture is one address"))
check("a dimmer is shown as a dimmer", cell(type="S4 26", dimmer="17"), ("17", "dimmer"))
check("the address wins over a dimmer",
      cell(type="S4 26", address="45", dimmer="99")[0], "45")
check("neither says so rather than sitting empty",
      cell(type="S4 26")[0], "—")
# ⚠ A known footprint that will not fit must say so, not quietly show a start.
check("a range running past 512 is explained",
      "past the end of the universe" in
      cell(type="Lustr 26 EDLT", address="2/500", profile="HSI Plus 7")[1], True)

print("\nthe shapes real plots are actually written in")

# 🔴 THE ADDRESS IS SOMETIMES A NUMBER. samples/demo.plot.json writes plain
# addresses as ints and universe addresses as "2/21", and typing the field as
# str alone made pydantic reject the whole request with a 422. That did not
# merely blank this column: /compute returns throws, pools and footcandles in
# the same call, so one annotation emptied the entire schedule. Caught in a
# browser, not here — which is why it is here now.
check("an integer address is accepted", cell(type="S4 26", address=45)[0], "45")
check("an integer dimmer is accepted", cell(type="S4 26", dimmer=17)[0], "17")
check("an integer address still ranges",
      cell(type="Lustr 26 EDLT", address=100, profile="HSI")[0], "100-105")

# 🔴 And the whole request must survive a plot written that way, not just this
# one field — a 422 here takes the throws and the pools with it.
_mixed = [dict(B, unit=1, channel=1, type="S4 26", address=45),
          dict(B, unit=2, channel=2, type="Lustr 26 EDLT", address="2/21", profile="HSI"),
          dict(B, unit=3, channel=3, type="S4 26", dimmer=17)]
_r = client.post("/compute", json={"instruments": _mixed})
check("a plot mixing int and string addresses computes", _r.status_code, 200)
check("...and the throws survive it",
      all("throw" in row or not row.get("computed") for row in _r.json()["instruments"]), True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
