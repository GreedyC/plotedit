#!/usr/bin/env python3
"""Read IESNA LM-63 photometric files.

Some manufacturers publish a datasheet with no numbers but an IES file with all
of them — Altman is the case in point. Their Spectra Cyc datasheet carries no
candela, no footcandles and no beam angle, but `SSCYC100_IES_2018-04-20.zip`
holds a full 46 x 73 goniometric measurement from Radiant Vision Systems.

    from plotedit.ies import read
    p = read("SSCYC100-RGBA_2018-04-22.ies")
    p["max_candela"], p["lumens"], p["watts"], p["beam_angle"], p["field_angle"]

⚠ BEAM AND FIELD ANGLES ARE ONLY MEANINGFUL FOR A SYMMETRIC BEAM. A cyc light
has an asymmetric reflector on purpose, so `symmetric` comes back False and the
angles describe the vertical plane through the peak — useful, but not the same
thing as an ellipsoidal's beam angle. The caller has to know the difference.
"""
import re


def _numbers(text):
    """IES packs numbers across lines freely; read them as one stream."""
    for tok in re.split(r"[\s,]+", text):
        if tok:
            try:
                yield float(tok)
            except ValueError:
                pass


def read(path_or_text):
    """Parse an IES file. Accepts a path or the text itself."""
    if "\n" in str(path_or_text):
        text = path_or_text
    else:
        text = open(path_or_text, encoding="latin-1").read()

    keywords = dict(re.findall(r"^\[(\w+)\]\s*(.*)$", text, re.M))

    m = re.search(r"^TILT\s*=\s*(\S+)\s*$", text, re.M | re.I)
    if not m:
        raise ValueError("no TILT line — this is not an IES file")
    if m.group(1).upper() != "NONE":
        raise ValueError("TILT data is present and is not handled")

    n = _numbers(text[m.end():])
    n_lamps = int(next(n))
    lumens_per_lamp = next(n)
    multiplier = next(n)
    n_vert = int(next(n))
    n_horiz = int(next(n))
    photometric_type = int(next(n))
    units_type = int(next(n))          # 1 = feet, 2 = meters
    width, length, height = next(n), next(n), next(n)
    ballast_factor = next(n)
    _future = next(n)
    watts = next(n)

    vert = [next(n) for _ in range(n_vert)]
    horiz = [next(n) for _ in range(n_horiz)]
    # candela grid: one row of n_vert values per horizontal angle
    grid = [[next(n) * multiplier * ballast_factor for _ in range(n_vert)]
            for _ in range(n_horiz)]

    peak = max(max(row) for row in grid)
    # where the peak is
    pk_h = max(range(n_horiz), key=lambda h: max(grid[h]))
    pk_v = max(range(n_vert), key=lambda v: grid[pk_h][v])

    # Is it symmetric? Compare each horizontal slice's peak against the overall.
    slice_peaks = [max(row) for row in grid]
    spread = (max(slice_peaks) - min(slice_peaks)) / peak if peak else 0
    symmetric = spread < 0.15

    beam = _angle_at(vert, grid[pk_h], peak * 0.50)
    field = _angle_at(vert, grid[pk_h], peak * 0.10)

    return {
        "keywords": keywords,
        "lamps": n_lamps,
        "lumens": round(lumens_per_lamp * n_lamps, 1) if lumens_per_lamp > 0 else None,
        "watts": watts or None,
        "max_candela": round(peak, 1),
        "peak_vertical_deg": vert[pk_v],
        "peak_horizontal_deg": horiz[pk_h],
        "symmetric": symmetric,
        "asymmetry": round(spread, 3),
        "beam_angle": beam,
        "field_angle": field,
        "vertical_angles": vert,
        "horizontal_angles": horiz,
        "candela": grid,
        "size_m": (width, length, height) if units_type == 2 else None,
        "units": "meters" if units_type == 2 else "feet",
        "photometric_type": {1: "Type C", 2: "Type B", 3: "Type A"}.get(photometric_type),
    }


def _angle_at(angles, values, threshold):
    """Full cone angle where intensity falls to `threshold`, by interpolation.

    Returns None when the distribution never falls that far inside the measured
    range — which happens on a wide asymmetric unit, and is honest: the answer
    is "wider than we measured", not a number.
    """
    peak_i = max(range(len(values)), key=lambda i: values[i])
    edges = []
    for direction in (1, -1):
        i = peak_i
        while 0 <= i + direction < len(values) and values[i + direction] > threshold:
            i += direction
        j = i + direction
        if not (0 <= j < len(values)):
            edges.append(None)
            continue
        v1, v2 = values[i], values[j]
        a1, a2 = angles[i], angles[j]
        t = 0 if v1 == v2 else (v1 - threshold) / (v1 - v2)
        edges.append(a1 + t * (a2 - a1))
    # 🔴 A ONE-SIDED SWEEP IS NOT A FAILURE. An ellipsoidal is measured from the
    # beam axis outward — 0° to 90° — so its peak sits at the FIRST sample and
    # walking the other way immediately runs off the array. That returned None
    # for every ellipsoidal IES ETC publish, while the Altman cyc worked because
    # an asymmetric unit is measured across its peak. So the reader had only
    # ever been exercised on the one fixture class it handled correctly.
    #
    # ⚠ Doubling is only valid when the measurement STARTS on the axis. If it
    # does, the distribution is symmetric about that axis by construction and
    # the full cone is twice the half angle. If it does not, an edge that ran
    # off really is unknown and None is still the honest answer.
    # ⚠ The test is where the SWEEP starts, not where the peak landed. On a
    # symmetric beam the brightest cell falls on 0° or 1.5° indifferently —
    # measurement noise — so keying off the peak missed most of the files. A
    # sweep that begins on the axis is the thing that means "measured outward
    # from centre", and that is what makes doubling correct.
    if angles and abs(angles[0]) < 1e-9 and edges[0] is not None and edges[1] is None:
        return round(2 * edges[0], 1)

    lo, hi = sorted(e for e in edges if e is not None) if all(e is not None for e in edges) else (None, None)
    if lo is None:
        return None
    return round(abs(hi - lo), 1)
