"""Print the stubs a new fixture type needs, in the places it needs them.

    python new_fixture.py "Chauvet Ovation E-260WW" --family "Ovation" --field 26

⭐ IT PRINTS RATHER THAN EDITS. A script that rewrites four tables would have to
guess where in each one an entry belongs, and the tables are grouped by maker and
by data source with comments explaining why. Pasting takes ten seconds and leaves
the contributor looking at the neighbours — which is where they will see that
every entry beside theirs names a document.

⚠ IT CANNOT INVENT NUMBERS. Every field it leaves blank is one only a datasheet
can fill. `validate_fixtures.py` refuses an entry with no source, so a stub
pasted in unfinished fails CI rather than shipping as a guess.
"""
import argparse

TEMPLATE_FIXTURE = '''    "{key}": dict(field={field}, beam={beam}, cd=None, ref_lamp="{lamp}",
                   family="{family}",
                   source="⚠ FILL THIS IN — maker, document title, revision or date, "
                          "and the page or table the numbers came from. An entry "
                          "with no source fails validate_fixtures.py."),'''

TEMPLATE_WATTS = '''    "{family}": {{"_typical": 0.0,   # ⚠ watts at typical draw
                 "_source": "⚠ FILL THIS IN — datasheet page"}},'''

TEMPLATE_ALIAS = '''    "{lower}": "{key}",'''

TEMPLATE_DMX = '''    "{key}": {{
        # ⚠ One entry per DMX profile the manual publishes, profile -> channel
        # count. Do NOT compute a count the manual does not state: the first
        # draft of the Series 2 table worked out HSI Plus 7 as 6 + 7 = 13 and
        # the datasheet says 15. A profile whose count is not published belongs
        # in UNPUBLISHED instead.
    }},'''

WHERE = [
    ("server/plotedit/photometrics.py", "FIXTURES",
     "Beside the nearest fixture from the same maker — the table is grouped by "
     "maker and by which document the numbers came from."),
    ("server/plotedit/photometrics.py", "FAMILY_WATTS",
     "Only if the family is new. Wattage belongs to the engine, not the lens, "
     "so one entry covers every lens in the family."),
    ("server/plotedit/fixture_names.py", "ALIASES",
     "Only if real paperwork spells it differently. Run "
     "`fixture_names.audit()` against your own Lightwright export first — most "
     "names resolve without help."),
    ("server/plotedit/dmx.py", "MODELS",
     "ONLY for a fixture that occupies more than one address. A conventional "
     "unit on a dimmer is one address and needs nothing here."),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", help='the key, e.g. "Chauvet Ovation E-260WW"')
    ap.add_argument("--family", default="⚠ FAMILY")
    ap.add_argument("--field", default="None", help="field angle in degrees (10%% of centre)")
    ap.add_argument("--beam", default="None", help="beam angle in degrees (50%% of centre)")
    ap.add_argument("--lamp", default="LED", help='ref_lamp, e.g. "HPL 750" or "LED"')
    ap.add_argument("--multi-address", action="store_true",
                    help="the fixture occupies more than one DMX address")
    a = ap.parse_args()

    print(f"\n{a.name}\n{'=' * len(a.name)}\n")
    blocks = [
        (WHERE[0], TEMPLATE_FIXTURE.format(key=a.name, field=a.field, beam=a.beam,
                                           lamp=a.lamp, family=a.family)),
        (WHERE[1], TEMPLATE_WATTS.format(family=a.family)),
        (WHERE[2], TEMPLATE_ALIAS.format(lower=a.name.lower(), key=a.name)),
    ]
    if a.multi_address:
        blocks.append((WHERE[3], TEMPLATE_DMX.format(key=a.name)))

    for (path, table, note), block in blocks:
        print(f"--- {path} · {table}")
        print(f"    {note}\n")
        print(block, "\n")

    print("Then, in order:")
    print("  1. python validate_fixtures.py     # refuses an unsourced entry")
    print("  2. python test_package.py          # the symbol and the pool")
    print("  3. Draw it on a plot and look at it. Nothing above checks that the")
    print("     symbol is the right SHAPE — only RP-2 and your eyes do that.")
    if not a.multi_address:
        print("\n⭐ No DMX entry: a unit on a dimmer occupies one address and needs none.")


if __name__ == "__main__":
    main()
