#!/usr/bin/env python3
"""Turn the names in real paperwork into keys in the photometric table.

Lightwright and Vectorworks carry names like `ETC Source4 36deg`,
`ETC CE Source4 PAR MCM (MFL)`, `S4-26° LED-ClrSrc`. `photometrics.FIXTURES` is
keyed `S4 36`, `S4 EA PAR MFL`, `Lustr 26 EDLT`. **None of the 38 distinct names
in Jerry's archive matched.** A plot imported from Lightwright drew correctly and
was silently unlit — every throw computed, every pool and footcandle blank.

Three layers, in order:

  1. NORMALISE   strip the manufacturer, unify Source4/S4/Source 4, deg/°,
                 repair mojibake, collapse punctuation. Catches most of it.
  2. ALIASES     explicit, for what normalising cannot reach.
  3. NO_DATA     names that ARE real fixtures but have no photometrics on file.
                 These must resolve to a REASON, never to silence — "we have no
                 figures for an Altman 6" Fresnel" is useful; a blank cell is not.
"""
import re
import unicodedata

# --------------------------------------------------------------- normalising

_MAKERS = r"(etc\s*ce|etc|altman|strand|light\s*instr|chauvet|blizzard(\s+lighting)?|briteq|adj|american\s*dj|martin|robe|elation)"


def normalise(name):
    """A comparable form: no maker, no punctuation, Source4 -> s4, ° -> deg."""
    s = str(name or "")
    # Repair mojibake BEFORE Unicode normalisation. Old Lightwright and
    # Vectorworks exports wrote UTF-8 through a latin-1 pipe, so a degree sign
    # arrives as U+00C2 U+00B0. NFKD decomposes the U+00C2 into "A" + a
    # combining mark, so "S4-50<mojibake>" normalised to "s4 50a deg" and matched
    # nothing. Strip the stray U+00C2 first.
    s = s.replace("\u00c2\u00b0", "\u00b0").replace("\u00c2", "")
    s = unicodedata.normalize("NFKD", s)
    s = s.lower()
    s = re.sub(r"°", " deg ", s)
    s = re.sub(r"\bsource\s*4\b|\bsource4\b|\bs4\b", " s4 ", s)
    s = re.sub(_MAKERS, " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b(\d+)\s*deg\b", r"\1", s)            # "36 deg" -> "36"
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------ aliases

# Paperwork name (normalised) -> FIXTURES key. Only where the fixture really is
# the one we hold data for.
ALIASES = {
    # the CE units are the same optics as the domestic ones
    "s4 par mcm mfl": "S4 EA PAR MFL",
    "s4 par mcm wfl": "S4 EA PAR WFL",
    "s4 par mcm nsp": "S4 EA PAR NSP",
    "s4 par mcm vnsp": "S4 EA PAR VNSP",
    # ⚠ a PARNel is a zoom. The archive never records which end, so this maps to
    # the SPOT end — the conservative choice, since assuming the flood end would
    # over-state the pool. Set it per unit when it matters.
    "s4 parnel": "S4 PARNel @25",
    # ColorSource Spot. Lightwright writes these as "S4-26° LED-ClrSrc" — an S4
    # body with a ColorSource engine. ETC publishes 19/26/36/50 as EDLT only, so
    # that is what these resolve to; a standard tube would read a little lower.
    "s4 26 led clrsrc": "ColorSource Spot 26 EDLT",
    "s4 36 led clrsrc": "ColorSource Spot 36 EDLT",
    "s4 50 led clrsrc": "ColorSource Spot 50 EDLT",
    "s4 19 led clrsrc": "ColorSource Spot 19 EDLT",
    "colorsource spot 26": "ColorSource Spot 26 EDLT",
    "colorsource spot 36": "ColorSource Spot 36 EDLT",
    "colorsource cyc": "ColorSource CYC",
    # Altman Shakespeare: catalogue numbers S6-5 ... S6-50. "Altman" is stripped
    # by normalise(), so "Altman S6-30" arrives here as "s6 30".
    **{f"s6 {d}": f"Altman Shakespeare {d}" for d in (5, 10, 20, 30, 40, 50)},
    **{f"shakespeare s6 {d}": f"Altman Shakespeare {d}" for d in (5, 10, 20, 30, 40, 50)},
    # Source Four LED. Jerry confirmed 2026.09.23 that the eight on Wizard of Oz
    # (2022) were Lustrs — the 140w load distinguishes them from the 166w
    # ColorSource units in the same rig.
    # ⚠ ETC publishes 19/26/36 as EDLT ONLY, so these resolve to the EDLT rows.
    # A Lustr on a standard tube reads a little lower.
    "s4 led 26": "Lustr 26 EDLT",
    "s4 led 36": "Lustr 36 EDLT",
    "s4 led 19": "Lustr 19 EDLT",
    "s4 led 50": "Lustr 50 LT",
    # ⚠ "spectra cyc 50" is NOT here — see CORRECTIONS below. Jerry's paperwork
    # calls the Wizard of Oz units 50s and they were 100s.
    # Only the PLUS: the original Color Force II 72 is a dimmer unit, and its
    # figures are not these.
    "color force ii plus 72": "Chroma-Q Color Force II Plus 72",
    "colorforce ii plus 72": "Chroma-Q Color Force II Plus 72",
    "chroma-q color force ii plus 72": "Chroma-Q Color Force II Plus 72",
    "color force ii plus 72 border": "Chroma-Q Color Force II Plus 72 Border",
    "color force ii plus 72 cyc": "Chroma-Q Color Force II Plus 72 Cyc",
    "spectra cyc 100": "Altman Spectra Cyc 100 RGBA",
    "spectra cyc 100 rgba": "Altman Spectra Cyc 100 RGBA",
    "spectra cyc 100 rgbw": "Altman Spectra Cyc 100 RGBW",
    # bare "Spectra Cyc" with no model resolves to the 100, the only one with
    # real measured photometrics
    "spectra cyc": "Altman Spectra Cyc 100 RGBA",
}


# ── Corrections ──────────────────────────────────────────────────────────────
# Names in the paperwork that are WRONG, and what the fixture actually was.
#
# These sit apart from ALIASES deliberately. An alias says "this is another way
# of writing the same fixture" — a spelling. A correction says "the paperwork is
# mistaken" — a claim about the world. The second kind should be easy to find,
# easy to question and easy to reverse, so it does not get buried among the
# spellings and quietly outlive the reason for it.
#
# ⚠ Why a paperwork name can lose to a memory. In Lightwright the LOAD comes
# from the library entry for whatever fixture name was typed. So a row reading
# "Altman Spectra CYC 50 / 50w" is not the unit corroborating its own name — it
# is the library repeating the name back. The name and the wattage are ONE fact,
# not two, and one fact from 2022 does not outweigh the designer who hung them.
CORRECTIONS = {
    "spectra cyc 50": (
        "Altman Spectra Cyc 100 RGBA",
        "paperwork says 'Spectra Cyc 50'; Jerry confirmed 2026.09.23 that the "
        "Wizard of Oz units were 100s. RGBA assumed — the RGBW is 3% brighter "
        "and otherwise identical, and no row records which was hung.",
    ),
}

# Real fixtures with no photometrics on file, and why. The photometric table is
# built from ETC datasheets; nothing else has been fetched.
# ⭐ ALTMAN 6" FRESNEL — 65Q and 165Q, which share one photometric chart and
# differ only in the focus mechanism. Jerry's own paperwork writes it "6in Fres",
# which sat in NO_DATA as "no datasheet fetched" until he produced the datasheet
# on 2026.10.13.
#
# ⚠ A BARE NAME HAS TO PICK AN END, because a Fresnel is two rows. It picks
# @spot, following 's4 parnel' -> 'S4 PARNel @25' — the narrow end — and resolve()
# says which one it chose, so a reader can move it to @flood. Spot is also the
# safer error on a drawing: it draws a smaller pool than the unit may be giving,
# and coverage you did not know you had is a better surprise than coverage you
# thought you had.
FRESNEL_6 = {
    "65q": "Altman 65Q @spot",
    "165q": "Altman 65Q @spot",
    "6in fres": "Altman 65Q @spot",
    "6 fresnel": "Altman 65Q @spot",
    "fresnel 6": "Altman 65Q @spot",
    "65q spot": "Altman 65Q @spot",
    "165q spot": "Altman 65Q @spot",
    "6in fres spot": "Altman 65Q @spot",
    "65q flood": "Altman 65Q @flood",
    "165q flood": "Altman 65Q @flood",
    "6in fres flood": "Altman 65Q @flood",
}
ALIASES.update(FRESNEL_6)


NO_DATA = {
    "s4 jr zoom": "Source Four Jr — a different fixture; no datasheet fetched",
    "lekolite 26": "Strand LekoLite — no datasheet fetched",
    "lekolite 40": "Strand LekoLite — no datasheet fetched",
    "8in fresnel": "Altman 8\" Fresnel — no datasheet fetched",
    # ⚠ The HPL-socket version of the 65Q, which Altman sell and the datasheet's
    # own dimension drawing shows. Its LAMP INFORMATION table lists 90-HPL575 and
    # 90-HPL750 with NO correction factor and no rated lumens, so the BTN chart
    # does not transfer to it and nothing else is published. Aliasing it to the
    # BTN rows would promise light nobody has measured.
    "65q hpl": "Altman 65Q-HPL — the HPL-socket 6\" Fresnel; Altman publish no "
               "correction factor for the HPL rows, so its output is not on file",
    "sky cyc 3 cell": "Altman Sky Cyc — a cyc unit; photometrics are per-cell and not on file",
    "3 cell sky cyc right": "Altman Sky Cyc — not on file",
    "3 cell sky cyc center": "Altman Sky Cyc — not on file",
    "3 cell sky cyc left": "Altman Sky Cyc — not on file",
    "atmosfear tour hz": "a hazer — not a luminaire",
    "color strike m": "a strobe/blinder — not on file",
    "bt strobe 3000": "a strobe — not on file",
    "strobe": "a strobe — not on file",
}

_GENERIC = {"cyc", "cyc 1", "cyc wash", "cyc gobos", "cyclone"}


def resolve(name, fixtures=None):
    """Return (key, note). key is None when nothing can be resolved.

    The note always explains, so a caller can show WHY a unit has no level
    rather than leaving a blank cell.
    """
    if fixtures is None:
        from . import photometrics as ph
        fixtures = ph.FIXTURES

    raw = str(name or "").strip()
    if not raw:
        return None, "no instrument type given"

    # exact key first — a plot written by this tool uses the real keys
    if raw in fixtures:
        return raw, ""

    n = normalise(raw)
    if not n:
        return None, f"{raw!r} does not look like an instrument type"

    if n in _GENERIC:
        return None, f"{raw!r} names a system, not a fixture type"

    if n in CORRECTIONS:
        key, why = CORRECTIONS[n]
        # Lead with the word "corrected" so it cannot be mistaken for a
        # spelling match in a report of 200 instruments.
        return (key, f"corrected: {raw!r} read as {key!r} — {why}") if key in fixtures else (
            None, f"correction for {raw!r} points at {key!r}, which is not in the table")

    if n in ALIASES:
        key = ALIASES[n]
        return (key, f"{raw!r} read as {key!r}") if key in fixtures else (
            None, f"alias for {raw!r} points at {key!r}, which is not in the table")

    if n in NO_DATA:
        return None, f"{raw!r}: {NO_DATA[n]}"

    # normalised match against the table
    index = {normalise(k): k for k in fixtures}
    if n in index:
        return index[n], (f"{raw!r} read as {index[n]!r}" if index[n] != raw else "")

    # a bare ellipsoidal degree, e.g. "s4 36" from "ETC Source4 36deg"
    m = re.fullmatch(r"s4 (\d+)", n)
    if m and f"S4 {m.group(1)}" in fixtures:
        return f"S4 {m.group(1)}", f"{raw!r} read as 'S4 {m.group(1)}'"

    return None, f"{raw!r} is not in the fixture table and has no alias"


def audit(names, fixtures=None):
    """Resolve a list of names; return (resolved, unresolved) for reporting."""
    ok, bad = {}, {}
    for nm in names:
        key, note = resolve(nm, fixtures)
        (ok if key else bad)[nm] = key or note
    return ok, bad
