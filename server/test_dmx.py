#!/usr/bin/env python3
"""How many DMX addresses a fixture occupies, and the range that follows.

    cd server && python3 test_dmx.py
"""
import json
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


# The specific model, because a Series 1 and a Series 2 Lustr share a
# photometric key and do NOT share a personality list.
S2 = "Source Four LED Series 2"

print("the profile table, against the datasheet")
# ETC Source Four LED Series 2 datasheet p.11, read off the plate itself.
for profile, want in [("Direct", 10), ("HSIC", 7), ("HSI", 6),
                      ("RGB", 6), ("Studio", 6)]:
    check(f"{S2} {profile}", dmx.channels(S2, profile)[0], want)

# 🔴 NOT 6 + 7. The datasheet works this example itself: HSI with Plus 7 is a
# FIFTEEN channel profile — six HSI channels, a spare at 7, the Plus 7 on/off
# control at 8, and the seven native colours at 9-15. The first draft of the
# table computed 13 from the prose and was wrong by two.
check("Lustr HSI Plus 7 is 15, not 6+7", dmx.channels(S2, "HSI Plus 7")[0], 15)

# ⚠ Plus 7 is offered on RGB and HSIC too, but the datasheet publishes no count
# for them, and the arithmetic that looks obvious is what got HSI wrong.
check("RGB Plus 7 exists but is not counted",
      dmx.channels(S2, "RGB Plus 7")[0], None)
check("...and says to read it off the fixture",
      "read it off" in dmx.channels(S2, "RGB Plus 7")[1], True)

check("an unrecorded profile is not guessed", dmx.channels(S2, None)[0], None)
check("...and names the range it could be",
      "6 to 15" in dmx.channels(S2, None)[1], True)
check("a profile the fixture lacks is refused",
      dmx.channels(S2, "Nonsense")[0], None)
check("a fixture with no table returns none", dmx.channels("S4", "HSI")[0], None)
check("every entry cites a document",
      all(dmx.SOURCES.get(m) for m in dmx.MODELS), True)

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

print("\nthe specific model, because the same type can be two fixtures")

# ⭐ Jerry, 2026.09.26: the same instrument can have different personalities —
# and a Series 1 and a Series 2 Lustr are both "Lustr 26 EDLT" here, same lens
# and same optics, with different personality lists. Keying the lookup on the
# family would answer a Series 2 question with Series 1 data.
check("a family offers its known models", dmx.models_for("Lustr"), [S2])
check("a conventional family offers none", dmx.models_for("S4"), [])
check("a recorded model is used as given", dmx.resolve_model("Lustr", S2), (S2, None))

# ⚠ One known model is used when the plot does not say — and it SAYS it assumed.
_m, _note = dmx.resolve_model("Lustr", None)
check("one known model is used when unrecorded", _m, S2)
check("...and the assumption is stated, not silent", "assuming" in (_note or ""), True)
check("a family with no models resolves to nothing",
      dmx.resolve_model("S4", None)[0], None)

# Two units of the SAME type on DIFFERENT personalities, which is the whole point.
_pair = [dict(B, unit=1, channel=21, type="Lustr 26 EDLT", address="2/1",
              model=S2, profile="HSI Plus 7"),
         dict(B, unit=2, channel=22, type="Lustr 26 EDLT", address="2/21",
              model=S2, profile="HSI")]
_rows = client.post("/compute", json={"instruments": _pair}).json()["instruments"]
check("same type, first on HSI Plus 7", _rows[0]["patch"], "2/1-2/15")
check("same type, second on HSI", _rows[1]["patch"], "2/21-2/26")

check("an assumed model is declared in the cell",
      "assuming" in cell(type="Lustr 26 EDLT", address="2/21", profile="HSI")[1], True)
check("...and is not claimed when the model is recorded",
      "assuming" in cell(type="Lustr 26 EDLT", address="2/21", model=S2, profile="HSI")[1], False)

print("\nthe table the inspector builds its dropdowns from")
_t = client.get("/dmx").json()
check("the models are served", _t["family_models"]["Lustr"], [S2])
check("the personalities are served", "HSI Plus 7" in _t["profiles"][S2], True)
# ⚠ An unpublished personality is still OFFERED — a designer on RGB Plus 7 has
# to be able to record it. It is listed separately, not hidden.
check("unpublished ones are offered separately",
      "RGB Plus 7" in _t["unpublished"][S2], True)
check("...and are not in the counted list",
      "RGB Plus 7" in _t["profiles"][S2], False)
check("every served model cites a source", all(_t["sources"].get(m) for m in _t["profiles"]), True)

print("\nthe shipped demo actually demonstrates it")

# 🔴 IT DID NOT, FOR THREE RELEASES. The personality field shipped in v0.1.12 and
# samples/demo.plot.json recorded no model and no profile, so the demo showed a
# start address and an explanation of why there was no range. The program was
# right and the thing every tester opens demonstrated nothing. Same shape as the
# Eos export that succeeded and contained nothing: the code worked, the sample
# never exercised it.
import os as _os3
_demo = json.load(open(_os3.path.join(_os3.path.dirname(__file__), "..",
                                      "samples", "demo.plot.json")))
_lustrs = [i for i in _demo["instruments"] if "Lustr" in i.get("type", "")]
check("the demo has LED units to demonstrate with", len(_lustrs) >= 2, True)
check("...and every one records a model", all(i.get("model") for i in _lustrs), True)
check("...and a personality", all(i.get("profile") for i in _lustrs), True)

_r = client.post("/compute", json={"instruments": _demo["instruments"],
                                   "colorTextHeightFt": 0.5})
_by_ch = {i["channel"]: row for row, i in zip(_r.json()["instruments"], _demo["instruments"])}
check("the demo shows a real range, not a start address",
      all("-" in _by_ch[i["channel"]]["patch"] for i in _lustrs), True)

# ⭐ TWO IDENTICAL FIXTURES ON DIFFERENT PERSONALITIES. That is the reason the
# field is on the unit rather than the type, and a demo that put both on the same
# one would not show it.
check("...on two different personalities",
      len({i["profile"] for i in _lustrs}) > 1, True)
check("...which give two different footprints",
      len({_by_ch[i["channel"]]["patch"] for i in _lustrs}) > 1, True)

# ⚠ And the ranges must not overlap each other, or the demo teaches a patch that
# would fight itself on a real rig.
def _span(txt):
    a, _, b = txt.partition("-")
    f = lambda t: int(t.split("/")[-1])
    return f(a), f(b or a)
_spans = sorted(_span(_by_ch[i["channel"]]["patch"]) for i in _lustrs)
check("...and the two ranges do not overlap",
      all(a[1] < b[0] for a, b in zip(_spans, _spans[1:])), True)

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    for f in FAILS:
        print("   ", f)
    sys.exit(1)
print("all passed")
