"""Check every fixture type the repo claims to know about.

⭐ THIS EXISTS SO REVIEW CAN BE MECHANICAL. A contributed fixture arrives as
numbers in four tables, and a reviewer reading a diff cannot see that a field
angle is smaller than its beam angle, or that a family was named that nothing
carries wattage for. A person checks what they think to check. This checks the
same things every time.

⚠ IT CANNOT TELL YOU A NUMBER IS RIGHT. Only that it is present, sourced,
internally consistent and reachable. The document behind it is still the
reviewer's job — which is why a missing `source` is the one failure here that
is never a warning.

Run it: `python validate_fixtures.py`. Exits 1 on a failure, 0 on warnings only,
so CI can gate on it.
"""
import sys
from plotedit import photometrics as P, fixture_names as N, dmx

FAILS, WARNS = [], []


def fail(where, msg):
    FAILS.append(f"{where}: {msg}")


def warn(where, msg):
    WARNS.append(f"{where}: {msg}")


# ------------------------------------------------------------- photometrics
#
# ⚠ field is the angle to 10% of centre intensity, beam the angle to 50%. The
# 50% cone is always INSIDE the 10% cone, so field < beam is not a debatable
# reading — it is two numbers entered the wrong way round, and it silently
# shrinks every pool the fixture draws.
for kind, f in P.FIXTURES.items():
    at = f"FIXTURES[{kind!r}]"

    if not f.get("source"):
        fail(at, "no source. Every figure names the document it came from.")

    # ⚠ NO ANGLES IS A LEGAL ANSWER. A cyc unit is asymmetric and its makers
    # publish no beam angle at all, which is why the first run of this script
    # "failed" three entries that were right. What is NOT legal is a 50% cone
    # with no 10% cone around it: field=None with a beam set means the wider
    # figure was lost, and every pool drawn from it is too small.
    field, beam = f.get("field"), f.get("beam")
    if field is None and beam is not None:
        fail(at, f"beam={beam} with no field. The 10° cone cannot be narrower than the 50° one.")
    elif field is None:
        if "no beam angle" not in f.get("source", "").lower() \
                and "no photometrics" not in f.get("source", "").lower():
            warn(at, "no angles, and the source does not say the maker publishes none")
    elif beam is None:
        warn(at, f"field={field} but no beam angle — pools will be drawn from the field alone")
    else:
        if not 0 < beam <= field < 180:
            fail(at, f"angles out of order or out of range: beam={beam} field={field}")
        if field > 120:
            warn(at, f"field={field}° is very wide — check it is degrees, not a ratio")

    cd = f.get("cd")
    if cd is not None and cd <= 0:
        fail(at, f"candela must be positive or None, got {cd}")

    # ⚠ ONLY TUNGSTEN. A lamp multiplier is the ratio between the tube ETC
    # measured at and the one actually in the fixture, and an LED has no tube —
    # its output changes with mode, which FAMILY_WATTS handles. Warning about
    # every LED here fired 24 times on the first run and buried the two warnings
    # that meant something. A validator nobody reads is worse than none.
    lamp = f.get("ref_lamp")
    if lamp and not lamp.upper().startswith("LED") \
            and lamp not in P.LAMP_MF and lamp != P.DEFAULT_LAMP:
        warn(at, f"ref_lamp {lamp!r} has no row in LAMP_MF, so no multiplier can be applied")

    fam = f.get("family")
    if not fam:
        fail(at, "no family. The symbol picker and the wattage table are both keyed on it.")
    elif fam not in P.FAMILY_WATTS and fam not in P._TUNGSTEN_FAMILIES:
        warn(at, f"family {fam!r} carries no wattage — a load table will be silent about it")

# Wattage entries need provenance too, and a family with no typical draw cannot
# answer the only question the table exists to answer.
for fam, w in P.FAMILY_WATTS.items():
    at = f"FAMILY_WATTS[{fam!r}]"
    if not w.get("_source"):
        fail(at, "no _source")
    if "_typical" not in w:
        fail(at, "no _typical, so watts_for() has no fallback")
    for k, v in w.items():
        if not k.startswith("_") and (not isinstance(v, (int, float)) or v <= 0):
            fail(at, f"mode {k!r} is not a positive wattage: {v!r}")

# -------------------------------------------------------------------- names
#
# An alias that points at nothing is worse than no alias: the name resolves,
# the fixture draws, and the photometrics are silently absent.
for src, dst in N.ALIASES.items():
    if dst not in P.FIXTURES:
        fail(f"ALIASES[{src!r}]", f"points at {dst!r}, which is not in FIXTURES")
# ⚠ A CORRECTION is (target, reason), not a bare name — the reason is the point
# of the table. The first version of this script read the tuple as a name and
# reported a correct entry as broken.
for src, entry in N.CORRECTIONS.items():
    at = f"CORRECTIONS[{src!r}]"
    dst, why = entry if isinstance(entry, tuple) else (entry, None)
    if dst not in P.FIXTURES and dst not in N.ALIASES:
        fail(at, f"points at {dst!r}, which resolves to nothing")
    if not why:
        fail(at, "no reason recorded. A correction that cannot be argued with is a guess.")

# ---------------------------------------------------------------------- dmx
for model, profiles in dmx.MODELS.items():
    at = f"MODELS[{model!r}]"
    if not profiles:
        fail(at, "no profiles")
    for prof, n in profiles.items():
        if not isinstance(n, int) or not 1 <= n <= 512:
            fail(at, f"{prof!r} is {n!r} — a footprint must be 1..512")
    # ⚠ A profile cannot be both published and unpublished. If it is in both
    # tables the count wins silently, and the warning the user should have seen
    # never appears.
    for prof in dmx.UNPUBLISHED.get(model, ()):
        if prof in profiles:
            fail(at, f"{prof!r} is in both MODELS and UNPUBLISHED")

for fam, models in dmx.FAMILY_MODELS.items():
    for m in models:
        # ⚠ A model with no profiles is legal ONLY if NO_FOOTPRINT says why.
        # Otherwise it is an entry someone started and did not finish, and the
        # dropdown offers a choice that answers nothing.
        if m not in dmx.MODELS and m not in dmx.NO_FOOTPRINT:
            fail(f"FAMILY_MODELS[{fam!r}]",
                 f"offers {m!r}, which has no profiles and no NO_FOOTPRINT reason")
    if fam not in P.FAMILY_WATTS:
        warn(f"FAMILY_MODELS[{fam!r}]", "is not a family the wattage table knows")

# ------------------------------------------------------------------- report
print(f"{len(P.FIXTURES)} fixtures · {len(P.FAMILY_WATTS)} families · "
      f"{len(N.ALIASES)} aliases · {len(dmx.MODELS)} DMX models\n")
for w in WARNS:
    print(f"  warn  {w}")
for f_ in FAILS:
    print(f"  FAIL  {f_}")
print()
if FAILS:
    print(f"{len(FAILS)} failure(s), {len(WARNS)} warning(s)")
    sys.exit(1)
print(f"every fixture is sourced, consistent and reachable — {len(WARNS)} warning(s)")
