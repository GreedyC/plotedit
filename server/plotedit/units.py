#!/usr/bin/env python3
"""Feet or metres, and the one place that knows the difference.

⭐ Jerry, 2026.09.25, after a designer in the UK asked whether it would "cross
the pond": work out what metric needs.

⭐ THE PHYSICS IS ALREADY METRIC. Illuminance is candela ÷ distance², so the
same published candela gives FOOTCANDLES when the distance is in feet and LUX
when it is in metres. Same table, same formula, same gel percentages, same beam
angles. Nothing in photometrics.py needs re-sourcing — this module only changes
what a number is CALLED and how it is written down.

⚠ FEET STAY THE STORED UNIT. Every saved plot, every test fixture and the whole
RP-2 symbol geometry are in feet, and a Source Four is 22 inches long in
Birmingham too. Converting at the edges is also what the DXF importer already
does — it takes mm, cm or m and stores feet. One canonical unit, conversion only
where a human reads or types.

🔴 THE DANGER IS DOUBLE CONVERSION, and it is silent: a length converted twice
is out by a factor of 10.76 and still looks like a plausible room. Every
function here converts exactly once, at a boundary, and the round-trip tests
exist to pin that down.
"""

# Exact by definition since 1959, not a measurement.
M_PER_FOOT = 0.3048
FOOT_PER_M = 1.0 / M_PER_FOOT

# 1 fc = 1 lumen/ft²; 1 lx = 1 lumen/m². The ratio is exactly (1/0.3048)².
LUX_PER_FC = FOOT_PER_M ** 2          # 10.7639...

IMPERIAL, METRIC = "imperial", "metric"
SYSTEMS = (IMPERIAL, METRIC)


def system_of(plot) -> str:
    """Which system a plot is written in. Imperial unless it says otherwise, so
    every plot that already exists keeps reading the way it was drawn."""
    u = (plot or {}).get("units")
    return METRIC if str(u).lower().startswith("met") else IMPERIAL


# ---------------------------------------------------------------- lengths

def feet_to(value_ft, system):
    """Feet into whatever the reader uses. The number only — no unit on it."""
    return value_ft * M_PER_FOOT if system == METRIC else value_ft


def to_feet(value, system):
    """And back. The inverse of feet_to, which the round-trip test pins."""
    return value * FOOT_PER_M if system == METRIC else value


def fmt_length(value_ft, system=IMPERIAL):
    """A length as a reader of that system would write it.

    ⚠ Imperial rounds to the INCH and metric to the centimetre, because that is
    the precision each system is read at on a plot — not because one is coarser.
    """
    if value_ft is None:
        return "—"
    if system == METRIC:
        return f"{value_ft * M_PER_FOOT:.2f} m"
    neg = value_ft < 0
    inches = round(abs(value_ft) * 12)
    ft, inch = divmod(inches, 12)
    return f"{'-' if neg else ''}{ft}'-{inch}\""


# ---------------------------------------------------------- illuminance

def fmt_illuminance(fc, system=IMPERIAL):
    """Centre-beam level, in the unit that system reads.

    🔴 THE LABEL IS THE POINT. A UK designer shown "179 fc" over a lux number
    has been told something false in a way that looks authoritative. The number
    and its unit travel together or not at all.
    """
    if fc is None:
        return "—"
    return f"{fc * LUX_PER_FC:.0f} lx" if system == METRIC else f"{fc:.0f} fc"


# --------------------------------------------------------- drawing scale

# Imperial: inches of paper per foot of building. Metric: a pure RATIO, with no
# units on either side — which is the one real structural difference between the
# two, not a conversion.
IMPERIAL_SCALES = {"1/8": 0.125, "1/4": 0.25, "3/8": 0.375, "1/2": 0.5,
                   "3/4": 0.75, "1": 1.0}
METRIC_SCALES = ("1:100", "1:50", "1:25", "1:20", "1:10")


def scale_ratio(scale):
    """Any scale as a plain ratio — 48 means one unit of paper to 48 of building.

    ⭐ This is the bridge between the two systems, and it is exact: 1/4" = 1'-0"
    IS 1:48, because a foot is twelve inches and a quarter of an inch goes into
    twelve exactly forty-eight times. 1/8" is 1:96, 1/2" is 1:24. The test pins
    those, because if the bridge is wrong every metric drawing is wrong by a
    ratio nobody would think to check.
    """
    if isinstance(scale, str) and scale.startswith("1:"):
        return float(scale[2:])
    # ⚠ Say what is wrong and what is allowed. A bare KeyError here came back as
    # a 500 with a stack trace, and the scale that produced it was "3/16" — which
    # the PDF IMPORTER offers, because the scale a borrowed drawing was made at
    # is not the same question as the scale this plot is drawn at. Two honest
    # lists that a caller can easily confuse, so the error has to be readable.
    if isinstance(scale, str) and scale not in IMPERIAL_SCALES:
        raise ValueError(
            f'unknown scale "{scale}" — this plot can be drawn at '
            + ", ".join(f'{k}" = 1\'-0"' for k in IMPERIAL_SCALES)
            + ", or a metric ratio like 1:50")
    inches_per_foot = IMPERIAL_SCALES[scale] if isinstance(scale, str) else float(scale)
    return 12.0 / inches_per_foot


def points_per_foot(scale):
    """Points of paper per foot of building — what the drawing actually runs on.

    Both systems reduce to this, which is why scaled_pdf can keep one number.
    """
    return (12.0 / scale_ratio(scale)) * 72.0


# --------------------------------------------------------------- defaults

# 🔴 IDIOMATIC, NOT CONVERTED. Head height is 5'-6" imperial; a metric designer
# says 1.7 m, not 1.676 m. Converting the defaults produces numbers no European
# would ever type, and they then propagate into every drawing as evidence of a
# measurement nobody took. These are Jerry's to review.
POOL_PLANES = {
    IMPERIAL: [("", "head 5'-6\"", 5.5), ("face", "face 5'-2\"", 5.1667),
               ("seated", "seated 3'-6\"", 3.5), ("deck", "the deck", 0.0)],
    METRIC:   [("", "head 1.7 m", 1.7 * FOOT_PER_M),
               ("face", "face 1.6 m", 1.6 * FOOT_PER_M),
               ("seated", "seated 1.1 m", 1.1 * FOOT_PER_M),
               ("deck", "the deck", 0.0)],
}
