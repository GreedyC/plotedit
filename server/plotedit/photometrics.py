#!/usr/bin/env python3
"""
photometrics.py — throw, angle, pool and light level for every unit on the plot.

All distances in FEET. Angles in degrees. Illuminance in footcandles.

    from photometrics import FIXTURES, aim, pool, footcandles, lens_for, overlap

    a = aim(unit=(6, 20, 14), target=(10, 10, 5.5))
    # -> {'throw': 16.9, 'elevation': 30.2, 'pan': -68.2, 'horizontal': 14.6, 'drop': 8.5}
    pool("S4 26", a["throw"])          # field and beam diameter at the target
    footcandles("S4 26", a["throw"], lamp="HPL 575")
    lens_for(8.0, a["throw"])          # which Source Four barrel gives an 8' field pool at that throw

Sources: every fixture row says where its numbers came from. Candela figures
marked 'derived' were back-calculated from the datasheet's own fc-at-distance
table (fc x d^2), which agreed to within 1% across the four distances given.
Anything without a source is not in the table.
"""
import math
import re

# Field/beam angles and center-beam candela at the reference lamp.
# cd is at HPL 750W/115V unless noted. Use LAMP_MF to convert.
FIXTURES = {
    "S4 19":  dict(field=18.0, beam=15.0, cd=245000, ref_lamp="HPL 750", family="S4",
                   source="ETC Source Four 19° datasheet 7060L1007 vG (cd derived from fc table: 392fc@25'). ⚠ ETC Europe Beam Spread Table 2000-11-13 gives 14/17 (beam/field) for the same tube — older data, likely an earlier lens revision. The modern US datasheet is preferred; the difference matters most on the 36°"),
    "S4 26":  dict(field=25.0, beam=18.0, cd=176000, ref_lamp="HPL 750", family="S4",
                   source="ETC Source Four 26° datasheet (cd derived from fc table: 783fc@15'). ⚠ ETC Europe Beam Spread Table 2000-11-13 gives 17/24 (beam/field) for the same tube — older data, likely an earlier lens revision. The modern US datasheet is preferred; the difference matters most on the 36°"),
    "S4 36":  dict(field=34.0, beam=27.0, cd=90885, ref_lamp="HPL 750", family="S4",
                   source="ETC Source Four 36° datasheet (cosine table: 90,885 cd). ⚠ ETC Europe Beam Spread Table 2000-11-13 gives 23/33 (beam/field) for the same tube — older data, likely an earlier lens revision. The modern US datasheet is preferred; the difference matters most on the 36°"),
    "S4 50":  dict(field=50.0, beam=36.0, cd=45650, ref_lamp="HPL 750", family="S4",
                   source="ETC Source Four 50° datasheet 7060L1010 (cosine table: 45,650 cd; fc table agrees: 457fc@10')"),
    "S4 90":  dict(field=86.6, beam=79.0, cd=None, ref_lamp="HPL 750", family="S4",
                   source="ETC Source Four 90° datasheet (angles); candela not extracted"),
    # Standard lens tubes the modern US datasheets do not cover — from the ETC Europe
    # "Source Four Beam Spread Table", data issued 13-11-2000 (on file). Angles only;
    # that table carries no candela. Internally consistent: every published multiplier
    # matches 2*tan(angle/2) to within a rounding step.
    "S4 5":   dict(field=7.0, beam=5.0, cd=None, ref_lamp="HPL 750", family="S4",
                   source="ETC Europe Beam Spread Table 2000-11-13 (angles only, no candela)"),
    "S4 10":  dict(field=11.0, beam=8.0, cd=None, ref_lamp="HPL 750", family="S4",
                   source="ETC Europe Beam Spread Table 2000-11-13 (angles only, no candela)"),
    # Zooms, at the three focus positions the table gives.
    "S4 Zoom 15-30 @15": dict(field=17.0, beam=12.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    "S4 Zoom 15-30 @23": dict(field=23.0, beam=16.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    "S4 Zoom 15-30 @30": dict(field=31.0, beam=22.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    "S4 Zoom 25-50 @25": dict(field=27.0, beam=19.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    "S4 Zoom 25-50 @36": dict(field=37.0, beam=26.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    "S4 Zoom 25-50 @50": dict(field=49.0, beam=35.0, cd=None, ref_lamp="HPL 750", family="S4 Zoom",
                   source="ETC Europe Beam Spread Table 2000-11-13"),
    # PARNel and EA PAR are OVAL — the table gives a second axis for the EA PAR
    # (MFL 32/19 across, 23/13 the other way; WFL 48/27 across, 31/17 the other way).
    # Only the wide axis is stored; rotate the lens and the narrow axis applies.
    "S4 PARNel @25": dict(field=26.0, beam=12.0, cd=None, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13 (oval beam; wide axis)"),
    "S4 PARNel @45": dict(field=47.0, beam=29.0, cd=None, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13 (oval beam; wide axis)"),
    "S4 EA PAR VNSP": dict(field=18.0, beam=11.0, cd=382145, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13. ETC Source Four PAR EA datasheet Rev J 2020-12, HPL 750/115 (cd corroborated by its own fc table: 425fc@30'). ⚠ ANGLES here are still the 2000 Europe table; the 2020 sheet gives 9° beam / 17° field. ETC changed the PAR lenses in 2020, so the two describe different lens generations — the candela is the current product's, the angles are not. Jerry's call which to follow; changing the angles resizes pools on plots already drawn."),
    "S4 EA PAR NSP": dict(field=19.0, beam=11.0, cd=336740, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13. ETC Source Four PAR EA datasheet Rev J 2020-12, HPL 750/115 (cd corroborated by its own fc table: 539fc@25'). ⚠ ANGLES here are still the 2000 Europe table; the 2020 sheet gives 9° beam / 16° field. ETC changed the PAR lenses in 2020, so the two describe different lens generations — the candela is the current product's, the angles are not. Jerry's call which to follow; changing the angles resizes pools on plots already drawn."),
    "S4 EA PAR MFL": dict(field=32.0, beam=19.0, cd=135225, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13 (oval; narrow axis 23/13). ETC Source Four PAR EA datasheet Rev J 2020-12, HPL 750/115 (cd corroborated by its own fc table: 601fc@15'). ⚠ ANGLES here are still the 2000 Europe table; the 2020 sheet gives 18°/13° beam and 31°/23° field (H/V). ETC changed the PAR lenses in 2020, so the two describe different lens generations — the candela is the current product's, the angles are not. Jerry's call which to follow; changing the angles resizes pools on plots already drawn."),
    "S4 EA PAR WFL": dict(field=48.0, beam=27.0, cd=47270, ref_lamp="HPL 750", family="S4 PAR",
                   source="ETC Europe Beam Spread Table 2000-11-13 (oval; narrow axis 31/17). ETC Source Four PAR EA datasheet Rev J 2020-12, HPL 750/115 (cd corroborated by its own fc table: 739fc@8'). ⚠ ANGLES here are still the 2000 Europe table; the 2020 sheet gives 31°/20° beam and 51°/37° field (H/V). ETC changed the PAR lenses in 2020, so the two describe different lens generations — the candela is the current product's, the angles are not. Jerry's call which to follow; changing the angles resizes pools on plots already drawn."),

    "S4 26 EDLT": dict(field=25.0, beam=17.0, cd=182301, ref_lamp="HPL 750", family="S4 EDLT",
                   source="ETC EDLT datasheet: 182,301 cd, field mult .45"),
    "S4 36 EDLT": dict(field=34.0, beam=22.0, cd=98553, ref_lamp="HPL 750", family="S4 EDLT",
                   source="ETC EDLT datasheet: 98,553 cd, field mult .61"),
    # ETC Source Four LED Series 2 Lustr — from the Source Four LED Photometry Guide (74 pp, on file).
    #
    # ⚠ ETC PUBLISHES 19/26/36 ONLY AS EDLT. Across every array (Lustr, Daylight HD, Tungsten HD,
    # Studio HD) the guide's standard-tube entries are 5°, 10°, 14°, 70°, 90°, the 50° LT and the
    # zooms. There is NO published standard-tube data for the three angles that actually get hung,
    # and EDLT tubes are a premium option almost nobody specifies. The keys below say EDLT so
    # nothing is mistaken for a house fixture. A standard tube will read somewhat lower in candela.
    # If a job turns on it, ask ETC or meter the unit — do not interpolate.
    #
    # cd is "Regulated Full" (all emitters, consistent output); 'modes' has the others.
    # Regulated 3200K is the tungsten-look number to compare against an HPL. Boost is not
    # sustainable output.
    "Lustr 19 EDLT": dict(field=19.1, beam=18.6, cd=97163, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 104518, "Regulated Full": 97163, "Regulated 3200K": 84221, "Regulated 5600K": 59774},
                   source="ETC S4 LED Photometry Guide p6: Series 2 Lustr 19° EDLT"),
    "Lustr 26 EDLT": dict(field=27.7, beam=25.3, cd=61792, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 66470, "Regulated Full": 61792, "Regulated 3200K": 53561, "Regulated 5600K": 38014},
                   source="ETC S4 LED Photometry Guide p7: Series 2 Lustr 26° EDLT"),
    "Lustr 36 EDLT": dict(field=34.8, beam=33.0, cd=40058, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 43091, "Regulated Full": 40058, "Regulated 3200K": 34723, "Regulated 5600K": 24644},
                   source="ETC S4 LED Photometry Guide p7: Series 2 Lustr 36° EDLT"),
    "Lustr 50 LT": dict(field=50.1, beam=48.6, cd=18090, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 19460, "Regulated Full": 18090, "Regulated 3200K": 15681, "Regulated 5600K": 11129},
                   source="ETC S4 LED Photometry Guide p8: Series 2 Lustr LED 50° LT"),
    "Lustr 14": dict(field=15.4, beam=14.8, cd=156611, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 168466, "Regulated Full": 156611, "Regulated 3200K": 135750, "Regulated 5600K": 96347},
                   source="ETC S4 LED Photometry Guide p6: Series 2 Lustr 14°"),
    "Lustr 70": dict(field=70.4, beam=65.0, cd=10909, ref_lamp="LED Regulated Full", family="Lustr",
                   modes={"Boost Full": 11735, "Regulated Full": 10909, "Regulated 3200K": 9456, "Regulated 5600K": 6712},
                   source="ETC S4 LED Photometry Guide p8: Series 2 Lustr 70°"),
    # ETC ColorSource Spot — from the ColorSource Spot Photometry Guide (13 pp,
    # on file). Same pattern as the Lustr: ETC publishes 19/26/36/50 as EDLT
    # ONLY, and 5/10/14/70/90 on standard tubes. Modes are "Maximum Output"
    # (cd below), "At 3200K" and "At 5600K" — the 3200K figure is the one to
    # compare against a tungsten Source Four.
    "ColorSource Spot 5": dict(field=7.4, beam=7.0, cd=397563, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 397563},
                   source="ETC ColorSource Spot Photometry Guide p4"),
    "ColorSource Spot 10": dict(field=11.2, beam=10.7, cd=242720, ref_lamp="LED Maximum Output",
                   family="ColorSource",
                   modes={"Maximum Output": 242720, "At 3200K": 218731, "At 5600K": 228029},
                   source="ETC ColorSource Spot Photometry Guide p4"),
    "ColorSource Spot 14": dict(field=15.4, beam=15.0, cd=120344, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 120344},
                   source="ETC ColorSource Spot Photometry Guide p5"),
    "ColorSource Spot 19 EDLT": dict(field=19.6, beam=19.1, cd=75485, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 75485},
                   source="ETC ColorSource Spot Photometry Guide p5"),
    "ColorSource Spot 26 EDLT": dict(field=26.6, beam=25.1, cd=52210, ref_lamp="LED Maximum Output",
                   family="ColorSource",
                   modes={"Maximum Output": 52210, "At 3200K": 47050, "At 5600K": 49050},
                   source="ETC ColorSource Spot Photometry Guide p6"),
    "ColorSource Spot 36 EDLT": dict(field=35.2, beam=33.0, cd=29053, ref_lamp="LED Maximum Output",
                   family="ColorSource",
                   modes={"Maximum Output": 29053, "At 3200K": 26181, "At 5600K": 27294},
                   source="ETC ColorSource Spot Photometry Guide p6"),
    "ColorSource Spot 50 EDLT": dict(field=50.8, beam=46.9, cd=14370, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 14370},
                   source="ETC ColorSource Spot Photometry Guide p7"),
    "ColorSource Spot 70": dict(field=72.2, beam=64.8, cd=9005, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 9005},
                   source="ETC ColorSource Spot Photometry Guide p7"),
    "ColorSource Spot 90": dict(field=88.8, beam=70.2, cd=6894, ref_lamp="LED Maximum Output",
                   family="ColorSource", modes={"Maximum Output": 6894},
                   source="ETC ColorSource Spot Photometry Guide p8"),
    "ColorSource Spot 15-30 Zoom @15": dict(field=17.4, beam=15.4, cd=98331,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p8"),
    "ColorSource Spot 15-30 Zoom @23": dict(field=25.3, beam=22.9, cd=54694,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p9"),
    "ColorSource Spot 15-30 Zoom @30": dict(field=32.8, beam=28.2, cd=None,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p9 (angles; candela not extracted)"),
    "ColorSource Spot 25-50 Zoom @25": dict(field=28.9, beam=28.4, cd=41624,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p10"),
    "ColorSource Spot 25-50 Zoom @37": dict(field=37.8, beam=36.4, cd=26903,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p10"),
    "ColorSource Spot 25-50 Zoom @50": dict(field=48.3, beam=42.2, cd=17850,
                   ref_lamp="LED Maximum Output", family="ColorSource Zoom",
                   source="ETC ColorSource Spot Photometry Guide p11"),

    # ⚠ The ColorSource CYC has NO beam angle. ETC: "Beam angle range N/A
    # (asymmetrical)" — it is a cyc light with an asymmetric reflector, so a
    # field/beam pair is meaningless and no candela is published. It is listed
    # so it resolves to a REASON rather than looking unknown; 4,117 max lumens,
    # 42 LUXEON C LEDs, five colors (red, green, blue, indigo, lime).
    "ColorSource CYC": dict(field=None, beam=None, cd=None, ref_lamp="LED",
                   family="ColorSource CYC", lumens=4117, colors=5,
                   source="ETC ColorSource CYC datasheet revE: asymmetrical, "
                          "no beam angle published; 4,117 max lumens"),

    # ⚠ Altman Spectra Cyc 50 — like the ColorSource CYC, an asymmetric cyc light
    # with NO published beam angle. Worse: Altman publishes no candela and no
    # footcandle figures at all. Their own specification says "IES Photometric
    # files shall be available FROM THE MANUFACTURER" — on request, not on the
    # web. Both the datasheet and the spec are on file and neither carries a
    # number worth computing from.
    #
    # What IS known and useful: 1,661 max lumens (RGBA), 50 W, and — the one
    # fact that changes a plot — Altman designs it for use on FOUR-FOOT CENTERS.
    "Altman Spectra Cyc 50": dict(field=None, beam=None, cd=None, ref_lamp="LED",
                   family="Cyc", lumens=1661, colors=4, spacing_ft=4.0,
                   source="Altman SSCYC50 datasheet rev2 2020-10-08 + specification "
                          "2020-07-31: asymmetrical, NO photometrics published. "
                          "Altman publishes IES for the 100 and 200 but NOT the 50 — see "
                          "'Altman Spectra Cyc 100 RGBA', whose figures are real. "
                          "NOTE: Jerry's paperwork name 'Spectra Cyc 50' no longer resolves here - "
                          "he confirmed 2026.09.23 the units were 100s. This row stays for a real 50. "
                          "Designed for 4-foot centers."),

    # ⭐ Altman Spectra Cyc 100 — the ONE fixture here whose figures come from a
    # real goniometric measurement rather than a datasheet table. Altman publish
    # no numbers for the Spectra Cyc range, but they DO publish IES files for the
    # 100 and 200: a 46 x 73 measurement by Radiant Vision Systems, 2018.
    # Parsed by ies.py; the datasheet corroborates the lumens exactly.
    #
    # ⚠ Asymmetric on purpose — 0.91 asymmetry, peak intensity at 70° off nadir,
    # because it stands at the base of a cyc and throws UP it. The beam and field
    # angles below describe the vertical plane through that peak. They are NOT
    # comparable to an ellipsoidal's, and wash_spacing() must not be used on it.
    "Altman Spectra Cyc 100 RGBA": dict(field=86.5, beam=32.4, cd=4612, ref_lamp="LED RGBA",
                   family="Cyc", lumens=4727, watts=94.1, colors=4, spacing_ft=4.0,
                   asymmetric=True, peak_vertical_deg=70.0,
                   source="Altman SSCYC100-RGBA IES, Radiant Vision Systems 2018-04-20 "
                          "(46x73 goniometric); datasheet SSCYC100 rev1 confirms 4,727 lm / 100 W. "
                          "ASYMMETRIC — angles are the vertical plane through the peak at 70°."),
    "Altman Spectra Cyc 100 RGBW": dict(field=86.5, beam=32.4, cd=4739, ref_lamp="LED RGBW",
                   family="Cyc", lumens=4856, watts=94.6, colors=4, spacing_ft=4.0,
                   asymmetric=True, peak_vertical_deg=70.0,
                   source="Altman SSCYC100-RGBW IES, Radiant Vision Systems 2018-04-09 "
                          "(46x73 goniometric); datasheet confirms 4,856 lm / 100 W. "
                          "ASYMMETRIC — angles are the vertical plane through the peak at 70°."),

    # Jerry's own two units. ⚠ Their CANDELA is unpublished and is staying that
    # way — Jerry, 2026.09.23: "forget the SHEHDS units, that was a one off."
    # Not an open task, not something to measure, not to be raised again. They go
    # on specials and isolated areas where a computed level was never the point.
    #
    # The WATTAGE is known and is worth having: 350W each, from the model name
    # and from his own venue notes for Without Consent, which planned a separate
    # circuit around it. That makes them count properly in a load table.
    "SHEHDS 19": dict(field=19.0, beam=None, cd=None, ref_lamp="LED 350W", family="SHEHDS",
                   watts=350.0,
                   source="SHEHDS 350W RGBW Profile manual: 'Beam Angle 19°'. 350W from the "
                          "model and from Jerry's Without Consent rig notes. No output data "
                          "published and none being sought — a one-off, per Jerry 2026.09.23."),
}

# Candela multiplying factors from the ETC lamp tables (per barrel, 300-hr lamps).
# ⚠ A candela with no multiplier for the lamp actually in the fixture is a
# candela nobody can use. Jerry's Source Fours are HPL 575 unless noted
# (DEFAULT_LAMP below), so a fixture listed only under HPL 750 computes NOTHING
# on his plots — which is exactly how every PAR came out blank even after the
# candela was filled in. Add a fixture to HPL 575 as well, or it is not done.
LAMP_MF = {
    "HPL 750": {"S4 19": 1.00, "S4 26": 1.00, "S4 36": 1.00, "S4 50": 1.00,
                # ETC Source Four PAR EA datasheet Rev J 2020-12, page 4
                # ("Lamps" table, Cd MF columns). HPL 750/115 is the reference
                # the candela was measured at, so every factor there is 1.00.
                "S4 EA PAR VNSP": 1.00, "S4 EA PAR NSP": 1.00,
                "S4 EA PAR MFL": 1.00, "S4 EA PAR WFL": 1.00},
    "HPL 575": {"S4 19": 0.85, "S4 26": 0.78, "S4 36": 0.67, "S4 50": 0.79,
                # Same table, HPL 575/115 row. The factor differs per LENS —
                # .92 to .75 — so one number for the family would be wrong for
                # three of the four.
                "S4 EA PAR VNSP": 0.92, "S4 EA PAR NSP": 0.88,
                "S4 EA PAR MFL": 0.80, "S4 EA PAR WFL": 0.75},
    # ⭐ THE LOW-WATTAGE BURNER (Jerry, 2026.09.29). An ordinary 115 V lamp —
    # no doubler, no special dimmer. You put one in to halve the load and get
    # more units on a circuit, and you pay about a third of the light for it.
    #
    # 🔴 NOT THE DIMMER DOUBLING LAMP, which is the 550/77 below. The two get
    # confused because both are ways of fitting more rig onto less dimmer, but
    # they are different techniques: this one just draws less.
    "HPL 375": {"S4 19": 0.71, "S4 26": 0.66, "S4 36": 0.56, "S4 50": 0.66,
                # ETC Source Four 19/26/36/50 datasheets, "Lamps" table, row
                # HPL 375/115 (ETC part RT142), Cd MF column — and the same four
                # confirmed by the EDLT 19-26-36-50 datasheet p4.
                #
                # ⚠ NO PAR FIGURES, for the same reason as the 550/77: the PAR
                # EA datasheet is not on file.
                },
    # ⭐ THE DIMMER DOUBLING LAMP (Jerry, 2026.09.29). 550 W at SEVENTY-SEVEN
    # VOLTS — the low voltage is the whole point, not a typo. ETC Dimmer
    # Doubling runs two fixtures off one dimmer on opposite half-cycles, and a
    # 77 V burner is what makes full output from the halved RMS voltage.
    #
    # 🔴 IT IS NOT THE 375. Both are ways of getting more rig out of less
    # dimmer, which is why they get mixed up, but a 375 simply draws less on an
    # ordinary 115 V circuit. ETC's own table marks the difference: the asterisk
    # sits on the 77 V lamps and the footnote reads "77 Volt HPL lamps are for
    # use with ETC Dimmer Doubling technology only."
    #
    # ⚠ PUT ONE OF THESE ON AN ORDINARY DIMMER AND THE PAPERWORK LIES. The
    # footcandles below come out right, the rig comes out dim, and nothing here
    # can tell the difference — a doubled dimmer is a property of the CIRCUIT,
    # which the plot has no way to say yet. Noting doublers is on NEXT.md.
    "HPL 550/77": {"S4 19": 0.87, "S4 26": 0.77, "S4 36": 0.68, "S4 50": 0.81,
                   # ETC Source Four 19/26/36/50 datasheets, "Lamps" table, row
                   # HPL 550/77* (ETC part RT112), Cd MF column — and the same
                   # four confirmed independently by the Source Four EDLT
                   # 19-26-36-50 datasheet p4, which prints all four lenses in
                   # one row. Both agree to the digit.
                   #
                   # ⚠ NO PAR FIGURES. The PAR EA datasheet is not on file, so
                   # an EA PAR on a 550/77 computes nothing rather than guessing
                   # — see the warning above this table.
                   },
    "HPL 575X": {"S4 36": 0.56,          # long-life; other S4 tubes not extracted
                 # Same table, HPL 575/115X row: .56 across all four lenses.
                 "S4 EA PAR VNSP": 0.56, "S4 EA PAR NSP": 0.56,
                 "S4 EA PAR MFL": 0.56, "S4 EA PAR WFL": 0.56},

    # ⭐ THE RETROFIT BURNERS. Pull the HPL, drop a 4WRD in, and the same Source
    # Four is an LED — same tube, same angles — so it is a LAMP, and these are
    # its multipliers against the HPL 750 the candela was measured at.
    #
    # ⭐ COMPUTED FROM CANDELA, NOT LUMENS, WHICH IS THE WHOLE POINT. The 4WRD
    # datasheet publishes lumens per lens beside the HPL's, and dividing those
    # two columns looks like exactly this table. It is not: the lumen ratio and
    # the candela ratio differ by 13–16% here, because an LED array and a
    # filament do not fill a lens the same way. These are from ETC's own IES.
    #
    # ⚠ TWO ETC SOURCES DIVIDED BY EACH OTHER. The numerator is a Light Lab IES
    # file; the denominator is the candela already in FIXTURES, off ETC's
    # published tables. Both are ETC's figures for the same lens, which is the
    # best available — but it is a ratio ACROSS documents, not a multiplier ETC
    # printed, and that is worth knowing before quoting it to two decimals.
    #
    # ⚠ 120 V ONLY; the 230 V unit was not computed. Gallery and Daylight
    # Gallery draw the same 150 W and are dimmer — the 90+ CRI costs about 15%
    # of the light, which is the trade a designer is actually making.
    "Source 4WRD II": {
        "S4 19": 0.61, "S4 26": 0.56, "S4 36": 0.64, "S4 50": 0.69,
        "S4 26 EDLT": 0.63, "S4 36 EDLT": 0.64},
    "Source 4WRD II Gallery": {
        "S4 19": 0.52, "S4 26": 0.48, "S4 36": 0.54, "S4 50": 0.59,
        "S4 26 EDLT": 0.50, "S4 36 EDLT": 0.54},
    "Source 4WRD II Daylight Gallery": {
        "S4 19": 0.55, "S4 26": 0.51, "S4 36": 0.57, "S4 50": 0.62,
        "S4 26 EDLT": 0.58, "S4 36 EDLT": 0.58},
}

# ⭐ HOW MANY COLOURS A RETROFIT BURNER MAKES — which is what gets DRAWN.
#
# USITT's Lighting Documentation Recommended Practice (February 2025) draws an
# LED ellipsoidal as the ordinary ERS body with dots at the lamp housing, which
# is RP-2 §6.16's rule — "number of dots represent the number of different
# colors" — carried onto the ERS. Its own key reads "LED ERS 26-DEGREE
# (10-CHANNEL)".
#
# A 4WRD is fixed white, so it is ONE colour and one dot. Not zero: the dot is
# what says the barrel is an LED at all, and that is the whole reason to draw it.
#
# ⚠ THIS IS A LAMP FACT, NOT A DRAWING FACT, which is why it lives here beside
# LAMP_WATTS rather than in symbols.py. What symbols.py decides is where the
# dots go; how many there are is a property of the burner.
LAMP_COLORS = {
    "Source 4WRD II": 1,
    "Source 4WRD II Gallery": 1,
    "Source 4WRD II Daylight Gallery": 1,
}


def lamp_colors(lamp):
    """Colours this lamp makes, or None when it is not an LED source at all.

    None and 0 are different answers: None is "this is a tungsten lamp, draw
    nothing", and there is no lamp that makes zero colours.
    """
    return LAMP_COLORS.get(str(lamp or "").strip())


# ---------------------------------------------------------------- wattage
#
# ⭐ Wattage belongs to the ENGINE, not the lens tube, which is how ETC publish
# it — so it is keyed by family rather than repeated across 47 rows.
#
# ⚠ And an LED's draw DEPENDS ON ITS OUTPUT MODE. A ColorSource Spot is 160W at
# Maximum Output and 115W regulated to 3200K: a 28% difference, which is the
# difference between four and five on a 20-amp dimmer. A single number per
# fixture would be wrong most of the time.
FAMILY_WATTS = {
    "Lustr": {"_typical": 167.0,
              "_source": "ETC Source Four LED Series 2 datasheet p2: "
                         "'Wattage typical — Series 2 Lustr: 167'"},
    "Daylight HD": {"_typical": 248.0,
                    "_source": "ETC S4 LED Series 2 datasheet p2: 'Series 2 Daylight HD: 248'"},
    "Tungsten HD": {"_typical": 208.0,
                    "_source": "ETC S4 LED Series 2 datasheet p2: 'Series 2 Tungsten HD: 208'"},
    "ColorSource": {"Maximum Output": 160.0, "Regulated 3200K": 115.0,
                    "Regulated 5600K": 141.0, "At 3200K": 115.0, "At 5600K": 141.0,
                    "_typical": 160.0,
                    "_source": "ETC ColorSource Spot Photometry Guide: power consumption "
                               "column, consistent across every lens"},
    "ColorSource CYC": {"_typical": 133.0,
                        "_source": "ETC ColorSource CYC datasheet p2: "
                                   "'133 W / 1.4 W at 120 V'"},
}
FAMILY_WATTS["ColorSource Zoom"] = FAMILY_WATTS["ColorSource"]
# Jerry's own units. 350W each, from the model name and his own rig notes.
FAMILY_WATTS["SHEHDS"] = {"_typical": 350.0,
                          "_source": "SHEHDS 350W RGBW Profile — the model name, corroborated by Jerry's Without Consent rig notes"}

# Jerry, 2026.09.23: "ETC S4 incandescents are 575 watts unless noted — there
# are 750." So a Source Four with no lamp recorded is an HPL 575.
#
# ⚠ NOT the same thing as `ref_lamp`. That says which lamp ETC MEASURED the
# candela at (HPL 750), and it stays. This says what is actually in the fixture
# when the paperwork is silent. Conflating the two would either mis-state the
# output or mis-state the load.
DEFAULT_LAMP = "HPL 575"
_TUNGSTEN_FAMILIES = ("S4", "S4 Zoom", "S4 PAR", "PAR", "Fresnel", "Strip", "Cyc Tungsten")


def watts_for(kind, lamp=None, mode=None):
    """(watts, note) for one instrument. Never guesses; says what it used.

    Tungsten: the LAMP carries the wattage, defaulting to HPL 575.
    LED: the FAMILY carries it, and the MODE refines it where ETC publish that.
    """
    key, row, _ = lookup(kind)
    if row is None:
        return None, f"{kind!r} is not in the fixture table"
    fam = row.get("family") or ""

    if any(fam.startswith(f) for f in _TUNGSTEN_FAMILIES) and not str(row.get("ref_lamp", "")).startswith("LED"):
        use = lamp or DEFAULT_LAMP
        w = lamp_watts(use)
        if w is None:
            return None, f"{use!r} is not a lamp name, so no wattage"
        return w, (f"at {use}" if lamp else f"at {use} (assumed — S4s are 575 unless noted)")

    # A row's OWN wattage wins over the family's. The Spectra Cyc 100 carries
    # 94.1W straight off its IES file — a real measurement, better than any
    # family default — and looking only at FAMILY_WATTS made it invisible, so a
    # cyc counted as zero in a load table while the number sat in the row.
    own = row.get("watts")
    if own:
        return float(own), f"{key}: {row.get('source', '')[:120]}"

    table = FAMILY_WATTS.get(fam)
    if not table:
        return None, (f"no published wattage for the {fam or kind!r} family — "
                      f"get it from the datasheet rather than estimating")
    if mode and mode in table:
        return table[mode], f"{fam} at {mode} — {table['_source']}"
    w = table["_typical"]
    extra = "" if mode is None else f" ({mode!r} not published separately)"
    # Say whose figure it is. Most of this table is ETC's; the SHEHDS entry is
    # not, and a note that says "ETC's" about a fixture ETC never made is the
    # same class of error as a candela with the wrong lamp on it.
    return w, (f"{fam}, the published typical draw{extra}. ⚠ TYPICAL IS NOT PEAK — "
               f"for a capacity check use the highest mode. {table['_source']}")


# ⭐ LAMPS WHOSE WATTAGE IS PUBLISHED RATHER THAN NAMED. Every tungsten lamp
# carries its wattage in its name — HPL 575, FEL 1000 — which is why lamp_watts
# can read it. A retrofit LED burner does not: "Source 4WRD II" says nothing, and
# the number is in a datasheet like any other figure.
#
# ⚠ THIS IS A LAMP, NOT A FIXTURE. A Source Four with a 4WRD in it is still an
# S4 26 — same lens tube, same field and beam angles, same symbol. What changed
# is the source inside it. So it belongs here and NOT in FIXTURES, and the load
# table is the only place it changes the answer.
LAMP_WATTS = {
    "Source 4WRD II Gallery": (150.0, "Same body and driver as the standard "
        "unit — the datasheet gives one wattage for all three variants. The "
        "90+ CRI array is dimmer, not thriftier."),
    "Source 4WRD II Daylight Gallery": (150.0, "As the Gallery: same draw, "
        "5900 K array."),
    "Source 4WRD II": (150.0,
        "ETC Source 4WRD II datasheet p.2: '150 W/1.2 W (120 V)'. ⚠ The 230 V "
        "version is 175 W. Gallery and Daylight Gallery draw the same as the "
        "standard unit; they differ in CRI and output, not in draw."),
}


def lamp_watts(lamp):
    """Watts from a lamp name — "HPL 575" is 575W, and that is exact.

    ⭐ For a tungsten fixture the wattage belongs to the LAMP, not the body. The
    same Source Four is 575W or 750W depending on what is in it, so a wattage
    stored against the fixture would be wrong for half the rig. Reading it off
    the lamp name is not a guess: it is what the name means.

    Returns None for an LED mode or anything without a number, because an LED's
    draw belongs to the fixture and has to come from its datasheet.

    ⚠ It must NOT read a number out of just any string. "Regulated 3200K" is an
    LED output mode, and a loose search finds 3200 in it and calls it 3200 watts
    — a number that looks real, lands in a load total and trips a breaker. So a
    lamp name has to LOOK like one: a short letter code followed by its wattage,
    as every tungsten lamp is named (HPL 575, FEL 1000, EHG 750). Anything with
    a Kelvin figure is a colour temperature and is refused outright.
    """
    import re as _re
    t = str(lamp or "").strip()
    # A published figure beats reading the name, and is the only way a retrofit
    # LED burner can answer at all — nothing in "Source 4WRD II" is a wattage.
    if t in LAMP_WATTS:
        return LAMP_WATTS[t][0]
    if not t or _re.search(r"\d\s*K\b", t, _re.I):
        return None
    m = _re.match(r"^[A-Za-z]{2,4}[\s-]*(\d{2,4})", t)
    return float(m.group(1)) if m else None


FIELD_ANGLES_S4 = [5, 10, 14, 19, 26, 36, 50, 70, 90]   # the barrel family, nominal


def lookup(kind):
    """FIXTURES row for a name that may have come from paperwork.

    Returns (key, row, note). Paperwork calls a Source Four 26 `ETC Source4
    26deg`; the table calls it `S4 26`. See fixture_names.py — 81% of the names
    in the real archive need translating, and before this existed they silently
    produced no pool and no level.
    """
    from .fixture_names import resolve
    key, note = resolve(kind, FIXTURES)
    return (key, FIXTURES[key], note) if key else (None, None, note)


def aim(unit, target):
    """unit=(x, y, trim_ft), target=(x, y, height_ft). Returns throw, elevation, pan, horizontal, drop."""
    ux, uy, uz = unit; tx, ty, tz = target
    dx, dy, dz = tx - ux, ty - uy, uz - tz
    horiz = math.hypot(dx, dy)
    throw = math.hypot(horiz, dz)
    elevation = math.degrees(math.atan2(dz, horiz)) if horiz else 90.0   # 0 = level, 90 = straight down
    pan = math.degrees(math.atan2(dx, -dy))     # 0 = pointing "downstage" (-y), +ve = clockwise
    return dict(throw=throw, elevation=elevation, pan=pan, horizontal=horiz, drop=dz)


def diameter(throw, angle_deg):
    """Circle of light at right angles to the beam, for a given cone angle."""
    return 2 * throw * math.tan(math.radians(angle_deg) / 2)


def pool(kind, throw, elevation=None):
    """Field and beam diameter at the throw distance. With elevation, also the
    stretched length of the pool on a horizontal deck (the ellipse's long axis)."""
    _, f, _note = lookup(kind)
    if f is None:
        return {"field": None, "beam": None, "note": _note}
    out = dict(field=diameter(throw, f["field"]) if f["field"] else None,
               beam=diameter(throw, f["beam"]) if f["beam"] else None)
    if elevation is not None and f["field"]:
        e = math.radians(elevation); half = math.radians(f["field"]) / 2
        drop = throw * math.sin(e)                       # height of the unit above the target plane
        # where the near and far edges of the cone meet that plane, measured horizontally
        near = drop / math.tan(min(e + half, math.pi / 2 - 1e-6))
        far = drop / math.tan(e - half) if e - half > 0.01 else None   # shallow beam never lands
        out["on_deck_length"] = (far - near) if far is not None else None
    return out


def load_gels(path=None):
    """gels.csv beside this file: gel, name, transmission (0-1), source, added. Add rows as gels come up."""
    import csv, os
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "gels.csv")
    out = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            out[row["gel"].upper()] = dict(name=row["name"], t=float(row["transmission"]), source=row["source"])
    return out

GELS = load_gels()


def parse_gel(gel):
    """Read Jerry's color notation. Two separators, two different physical things:

        "R52+R119"  PLUS  = stacked, one gel on top of another in the same frame.
                            Transmissions MULTIPLY.
        "R52/R119"  SLASH = a split frame — two gels cut diagonally and put in
                            together, so each covers part of the beam. They do NOT
                            multiply; each half has its own transmission.

    Returns (kind, [gel names]) where kind is "stacked" or "split".
    A list or tuple is treated as stacked, which is what a frame usually holds.
    """
    if isinstance(gel, (list, tuple)):
        return "stacked", [str(g).strip() for g in gel]
    g = str(gel).strip()
    if "/" in g:
        return "split", [x.strip() for x in g.split("/") if x.strip()]
    return "stacked", [x.strip() for x in re.split(r"[+,]", g) if x.strip()]


def gel_factor(gel):
    """Transmission for a color string or list. Returns (factor, note).

    Stacked gels multiply. A SPLIT frame has no single factor — it returns the
    factor for the FIRST gel named and says so, because the beam is not uniform.
    Unknown gel -> (None, note) rather than a guess."""
    if not gel:
        return 1.0, ""
    kind, gels = parse_gel(gel)
    rows = []
    for g in gels:
        row = GELS.get(g.upper())
        if row is None:
            # ⚠ SAY WHAT A BARE NUMBER IS MISSING. R119 is Light Hamburg Frost
            # at 89% and L119 is Dark Blue at 2%: the same digits, opposite
            # filters. An unprefixed number is not a gel this can look up, and
            # guessing a house's preferred maker is how a plot promises forty
            # times the light it will deliver.
            if g[:1].isdigit():
                return None, (f"gel {g} has no maker — R{g} and L{g} are different "
                              f"filters. Write R{g} for Roscolux or L{g} for LEE.")
            return None, (f"gel {g} not in gels.csv — add it with the maker's "
                          f"published transmission")
        rows.append((g.upper(), row["t"]))
    if kind == "split":
        first = rows[0]
        others = ", ".join(f"{n} {t*100:.0f}%" for n, t in rows[1:])
        return first[1], (f"SPLIT FRAME — {first[0]} {first[1]*100:.0f}% on this part of the beam; "
                          f"{others} on the rest. No single level covers the whole pool")
    factor = 1.0
    for _, t in rows:
        factor *= t
    return factor, " + ".join(f"{n} {t*100:.0f}%" for n, t in rows)


def footcandles(kind, throw, lamp=None, mode=None, gel=None):
    """Center-beam illuminance = candela / throw², times gel transmission. Returns (fc, note).
    lamp: an HPL lamp for tungsten fixtures. mode: an output mode for LED fixtures with 'modes'.
    gel: a Rosco number or a list of them. Transmission figures are Rosco's, measured for a
    broadband (tungsten) source — exact for HPL, approximate on a white LED."""
    key, f, knote = lookup(kind)
    if f is None:
        return None, knote
    gf, gnote = gel_factor(gel)
    if gf is None: return None, gnote
    if gel and f["family"] not in ("S4", "S4 EDLT"):
        gnote += " (transmission is a tungsten figure; approximate on LED)"
    # use the RESOLVED key: the lamp multiplier table is keyed by table name,
    # not by whatever the paperwork called the fixture
    fc, note = _footcandles_white(f, key, throw, lamp, mode)
    if fc is None:
        return None, note
    if knote:
        note = f"{note} [{knote}]"
    return fc * gf, (note + (f", through {gnote}" if gel else ""))


def _footcandles_white(f, kind, throw, lamp, mode):
    _given = lamp is not None          # so the note can say when a lamp was assumed
    if mode and f.get("modes"):
        if mode not in f["modes"]:
            return None, f"{kind} has no mode '{mode}'; has {list(f['modes'])}"
        return f["modes"][mode] / throw ** 2, f"at {mode}"
    if not f["cd"]:
        return None, f"no candela on file for {kind} — {f['source']}"

    # ⭐ Jerry, 2026.09.23: "ETC S4 incandescents are 575 watts unless noted."
    # ETC MEASURED the candela at HPL 750, but a 750 is not what is in the
    # fixture. Computing an unstated lamp at the reference overstates every level
    # on the plot by about a quarter, in the safe-looking direction — the plot
    # promises light the rig will not deliver. So when the paperwork is silent
    # about a tungsten Source Four, assume the lamp that is actually in it.
    if lamp is None and f.get("ref_lamp") in LAMP_MF and kind in LAMP_MF.get(DEFAULT_LAMP, {}):
        lamp = DEFAULT_LAMP

    mf = 1.0; note = f"at {f['ref_lamp']}"
    if lamp and lamp != f["ref_lamp"]:
        mf = LAMP_MF.get(lamp, {}).get(kind)
        if mf is None:
            return None, f"no {lamp} multiplier on file for {kind}"
        note = f"at {lamp} (MF {mf})" + ("" if _given else " — assumed, S4s are 575 unless noted")
    return f["cd"] * mf / throw ** 2, note


def lens_for(pool_ft, throw, family="S4", use="field"):
    """Which barrel gives a pool of this size at this throw. Returns sorted (kind, diameter, error)."""
    rows = []
    for k, f in FIXTURES.items():
        if f["family"] != family or not f[use]: continue
        d = diameter(throw, f[use]); rows.append((k, d, d - pool_ft))
    return sorted(rows, key=lambda r: abs(r[2]))


def overlap(units, kind_key="kind", height=5.5):
    """Given units as dicts with x, y, trim, focus (x,y) and kind: do adjacent field
    pools meet at `height`? Returns list of (unit_a, unit_b, gap_ft) — negative gap = overlap."""
    pools = []
    for u in units:
        a = aim((u["x"], u["y"], u["trim"]), (u["focus"][0], u["focus"][1], height))
        r = pool(u[kind_key], a["throw"])["field"] / 2
        pools.append((u, u["focus"][0], u["focus"][1], r))
    out = []
    for i in range(len(pools)):
        for j in range(i + 1, len(pools)):
            (ua, xa, ya, ra), (ub, xb, yb, rb) = pools[i], pools[j]
            gap = math.hypot(xa - xb, ya - yb) - (ra + rb)
            out.append((ua.get("num", i + 1), ub.get("num", j + 1), gap))
    return out


def wash_spacing(kind, throw, rule="field-to-beam"):
    """On-center spacing for units in a wash, at the throw distance.

    Rules, all measured at the target plane:
      "field-to-beam"  (the usual practice) — each unit's FIELD edge lands on the
                       next unit's BEAM edge, so the overlap zone sits between the
                       two beams:  F{ (B) F{ } (B) }.  d = Rfield + Rbeam
      "beam-to-beam"   — beam edges just touch. Tighter, brighter, very even. d = 2*Rbeam
      "field-to-field" — field edges just touch. Widest; leaves a dim scallop
                       between pools because both units are at 10% there. d = 2*Rfield

    Returns dict with the spacing, the two radii, and the overlap width.
    """
    _, f, _note = lookup(kind)
    if f is None:
        raise ValueError(_note)
    if not f["field"] or not f["beam"]:
        raise ValueError(f"{kind} has no beam/field pair on file — {f['source']}")
    rf = diameter(throw, f["field"]) / 2
    rb = diameter(throw, f["beam"]) / 2
    d = {"field-to-beam": rf + rb, "beam-to-beam": 2 * rb, "field-to-field": 2 * rf}[rule]
    return dict(spacing=d, field_r=rf, beam_r=rb, overlap=max(0.0, 2 * rf - d),
                penumbra=rf - rb, rule=rule)


def wash_row(kind, throw, width, rule="field-to-beam"):
    """How many units to cover `width` feet of acting area, and where they sit.

    Returns (count, spacing, positions) with positions centered on the width.
    Count is rounded up, then the spacing is eased back so the row fits evenly.
    """
    import math
    w = wash_spacing(kind, throw, rule)
    covered = width - 2 * w["beam_r"]              # first and last units light their own beam out to the edge
    n = max(1, int(math.ceil(covered / w["spacing"])) + 1)
    actual = covered / (n - 1) if n > 1 else 0.0
    start = -(width / 2) + w["beam_r"]
    return dict(count=n, spacing=actual, ideal=w["spacing"], positions=[start + i * actual for i in range(n)],
                penumbra=w["penumbra"], rule=rule)


def fmt_ft(x, system=None):
    """A length as the plot's reader writes it. 12.5 -> 12'-6" or 3.81 m.

    ⚠ THE VALUE IS ALWAYS IN FEET. Feet are the internal unit throughout —
    every geometry, photometric and layout calculation works in them — and this
    is the boundary where that becomes a reader's number. Converting earlier
    would mean two sets of arithmetic to keep in step, and the one that is
    wrong would be the one nobody is looking at.

    `system` of None means imperial, so every existing caller is unchanged.
    """
    from . import units as _u
    return _u.fmt_length(x, system or _u.IMPERIAL)


def report(kind, unit, target, lamp=None, mode=None, gel=None):
    """One unit, all the numbers, as text."""
    a = aim(unit, target); p = pool(kind, a["throw"], a["elevation"]); fc, note = footcandles(kind, a["throw"], lamp, mode, gel)
    lines = [f"{kind}: throw {fmt_ft(a['throw'])}, elevation {a['elevation']:.0f}°, pan {a['pan']:+.0f}°",
             f"  field {fmt_ft(p['field'])} / beam {fmt_ft(p['beam'])} across"
             + (f", {fmt_ft(p['on_deck_length'])} long on the deck" if p.get("on_deck_length") else "")]
    lines.append(f"  {fc:.0f} fc center beam {note}" if fc else f"  light level: {note}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report("S4 26", (6, 20, 14), (10, 10, 5.5), lamp="HPL 575"))
    print(report("S4 36", (16.5, 20, 14), (16.5, 10, 5.5), lamp="HPL 575"))
    print(report("Lustr 26 EDLT", (27, 20, 14), (22, 10, 5.5), mode="Regulated 3200K"))
    print("8' pool at 17' throw:", [(k, round(d, 1)) for k, d, e in lens_for(8, 17)[:3]])


# ---------------------------------------------------------------- pool shape

def pool_shape(kind, unit, focus, plane_h=5.5, which="field", focus_h=5.5):
    """The REAL shape a beam makes on a horizontal plane — an ellipse, not a circle.

    ⭐ A cone only cuts a circle when it points straight down. At any other angle
    the intersection is an ellipse, elongated away from the unit, and the further
    off vertical the more extreme: a 26° field from 10' up at 30° elevation lands
    22 FEET LONG and 10 wide. Drawing that as a circle understates the far end of
    the pool by a factor of two, which is the end that lands on the scenery.

    `unit` is (x, y, trim); `focus` is (fx, fy) in plan. `plane_h` is the height
    of the plane to cut at — 0 for the deck, about 5'-6" for the top of a head,
    5'-2" for a face. `which` is "field" or "beam".

    Returns a dict with the semi-major `a`, semi-minor `b`, the ellipse CENTRE
    (cx, cy) — which is NOT the aim point, it sits beyond it — the plan `angle`
    of the major axis, and the near and far ground distances. Or a `note` saying
    why there is no ellipse.

    The geometry, with θ the elevation of the axis and α the half-angle:

        near = H / tan(θ + α)        far = H / tan(θ − α)
        a    = (far − near) / 2      b   = H·sin α / √(sin(θ+α)·sin(θ−α))

    Both reduce to H·tan α when θ = 90°, and the whole thing is checked against a
    200,000-ray numerical cast in the tests.
    """
    key, row, note = lookup(kind)
    if row is None:
        return {"note": note or f"{kind!r} is not in the fixture table"}
    ang = row.get(which)
    if not ang:
        return {"note": f"no {which} angle published for {key} — {row.get('source', '')[:80]}"}

    ux, uy, trim = unit[0], unit[1], unit[2]
    fx, fy = focus[0], focus[1]
    H = trim - plane_h
    if H <= 0:
        return {"note": f"the plane at {plane_h}' is at or above the unit at {trim}' "
                        f"— nothing to cut"}

    run = math.hypot(fx - ux, fy - uy)
    # ⚠ The AXIS elevation comes from where the unit is AIMED (focus_h), not from
    # the plane being cut. They are different things: aim a unit at a face and
    # then ask what it does on the deck, and the axis has not moved — the plane
    # has. Deriving θ from plane_h made the pool at the deck come out the same
    # size as the pool at head height, which is impossible: the beam is still
    # spreading on its way down.
    if run < 1e-9:
        theta = math.pi / 2
    else:
        theta = math.atan2(trim - focus_h, run)
    alpha = math.radians(ang) / 2.0

    if theta - alpha <= math.radians(0.25):
        return {"note": f"{key} at {math.degrees(theta):.0f}° elevation is GRAZING the "
                        f"plane at {plane_h}' — its far edge never lands, so the pool "
                        f"has no far end. Raise the trim or steepen the focus",
                "grazing": True}

    near = H / math.tan(theta + alpha)
    far = H / math.tan(theta - alpha)
    a = (far - near) / 2.0
    b = H * math.sin(alpha) / math.sqrt(math.sin(theta + alpha) * math.sin(theta - alpha))

    # Along the plan direction of the throw, from the unit outwards.
    if run < 1e-9:
        dx, dy, angle = 1.0, 0.0, 0.0
    else:
        dx, dy = (fx - ux) / run, (fy - uy) / run
        angle = math.degrees(math.atan2(dy, dx))
    mid = (near + far) / 2.0
    return {"a": a, "b": b, "cx": ux + dx * mid, "cy": uy + dy * mid,
            "angle": angle, "near": near, "far": far,
            "length": 2 * a, "width": 2 * b, "plane_h": plane_h, "which": which,
            "note": ""}
