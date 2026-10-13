#!/usr/bin/env python3
"""Check a plot for the things a person would catch by reading it carefully.

    cd server && python3 -m plotedit.qc ../samples/*.plot.json

⭐ WHY THIS EXISTS. Every defect found in the sample plots so far was found by
LOOKING at a drawing — the raked catwalk units, the dragged batten, the gel
punctuation that silently removed every footcandle figure. None of them showed
up in a diff, because a plot is 200 near-identical records and the eye slides
off it. These are the checks that do not need eyes.

⚠ ERROR vs WARNING is the whole design, and the line is not severity — it is
whether the finding is a FACT about the file or a judgement about the design:

  error   — the file contradicts itself, or says something impossible. Two units
            in one slot on a pipe. A position name with no position behind it.
  warning — something a designer might mean, and might not. No channel yet. A
            focus height nobody usually uses. Half a plot is warnings on the day
            you start drawing it, and that is correct.

🔴 So the CLI exits 1 on an error and 0 on warnings. A gate that goes red for an
unfinished plot is a gate that gets switched off.
"""
import collections
import json
import math
import sys

from . import fixture_names
from . import photometrics as ph
from . import positions

#: How far off its pipe a unit may sit before it counts as misplaced, in feet.
#: Six inches. A boom is a single point in plan and its units are drawn to the
#: side (RP-2 §6.12), so the distance is measured to the position's nearest leg,
#: and for a zero-length position that is the point itself.
ON_THE_RUN = 0.5

#: Focus heights that do not want a second look, in feet. The deck to the top of
#: a flown piece. Head height is 5'-6" and a shin buster is 1'-6", so the range
#: has to be wide; it is here to catch 0 and 55, not to have an opinion.
FOCUS_RANGE = (0.5, 20.0)

Finding = collections.namedtuple("Finding", "level check says units")


def _label(inst):
    pos = (inst.get("position") or "").strip() or "no position"
    return f"{pos} unit {positions.unit_label(inst.get('unit')) or '—'}"


def _channel(inst):
    ch = inst.get("channel")
    return "no channel" if ch is None else f"channel {ch}"


def _legs(plot):
    """Position name (folded) -> its legs. A catwalk is several legs, one name."""
    out = collections.defaultdict(list)
    for p in plot.get("positions") or []:
        out[str(p.get("name") or "").strip().lower()].append(p)
    return out


def _to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    span = dx * dx + dy * dy
    if span < 1e-12:                      # a boom: the position IS a point
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ─── errors: the file contradicts itself ──────────────────────────────────────

def duplicate_units(plot):
    """Two instruments in the same slot on the same pipe.

    ⚠ The unit number is WHERE IT HANGS, counted from one end — it is how the
    electrician finds it and how the hang sheet reads. Two unit 9s on #3
    Electric is not a clash to resolve later; one of them is in the wrong place
    and nobody can say which.
    """
    seen = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        # ⚠ The LABEL, not the raw value: 10 and "10" are one unit, and so are
        # "10a" and "10A". Keying on the raw value would let a plot hold two
        # unit 10s that the paperwork cannot tell apart and this check calls fine.
        label = positions.unit_label(inst.get("unit"))
        if label:
            seen[((inst.get("position") or "").strip(), label)].append(inst)
    out = []
    for (pos, unit), group in sorted(seen.items(), key=lambda kv: str(kv[0])):
        if len(group) > 1:
            out.append(Finding(
                "error", "duplicate-unit",
                f"{len(group)} instruments are unit {unit} on {pos or 'no position'}",
                [f"{_channel(i)} at ({i.get('x')}, {i.get('y')})"
                 for i in group]))
    return out


def unknown_positions(plot):
    """An instrument hung on a position the plot does not have.

    It still draws, at its own x and y — which is why this is invisible on the
    page. What breaks is every piece of paperwork, because the schedule and the
    hang sheet group by position, and this unit groups under a heading that
    exists nowhere else in the show.
    """
    legs = _legs(plot)
    missing = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        name = (inst.get("position") or "").strip()
        if name.lower() not in legs:
            missing[name].append(inst)
    return [Finding("error", "unknown-position",
                    f"{len(group)} instruments name the position {name!r}, "
                    f"which is not in the plot" if name else
                    f"{len(group)} instruments have no position",
                    [_label(i) for i in group])
            for name, group in sorted(missing.items())]


def off_the_run(plot, tol=ON_THE_RUN):
    """A unit sitting away from the pipe it says it is on.

    🔴 This is the shape of a bug already shipped once: a batten dragged and put
    back left its units off the run, and it was found by looking at the plot.
    """
    legs, out = _legs(plot), []
    for inst in plot.get("instruments") or []:
        here = legs.get((inst.get("position") or "").strip().lower())
        if not here or inst.get("x") is None or inst.get("y") is None:
            continue
        gap = min(_to_segment(inst["x"], inst["y"],
                              p.get("x1", 0), p.get("y1", 0),
                              p.get("x2", 0), p.get("y2", 0)) for p in here)
        if gap > tol:
            out.append((gap, inst))
    return [Finding("error", "off-the-run",
                    f"{len(out)} instruments sit more than "
                    f"{ph.fmt_ft(tol)} off the position they name",
                    [f"{_label(i)} — {ph.fmt_ft(g)} away"
                     for g, i in sorted(out, reverse=True, key=lambda gi: gi[0])])
            ] if out else []


def unknown_types(plot):
    """A type the fixture table cannot resolve, even by alias.

    ⚠ It fails quietly and completely: no beam angle, so no pool, no throw and
    no footcandles — the unit draws as a symbol and promises light nobody has
    computed. That is the gel bug again in a different coat.
    """
    bad = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        key, note = fixture_names.resolve(inst.get("type"))
        if not key:
            bad[note].append(inst)
    return [Finding("error", "unknown-type", note, [_label(i) for i in group])
            for note, group in sorted(bad.items())]


# ─── warnings: something a designer might mean ────────────────────────────────

def focus_heights(plot):
    """A focus height at the deck, or outside the range anyone aims at.

    ⚠ 0 IS NOT THE SAME AS BLANK, and this is the trap. Blank means head height
    — `focusH ?? 5.5` in the web app. Zero is a number, so it travels, and the
    plot then computes every pool and every footcandle at the FLOOR: on a 30'
    electric that is a 30' throw instead of 24'-6", and a pool the wrong size on
    every sheet. A plot can look entirely finished and be wrong by that much.
    """
    low, high = FOCUS_RANGE
    deck, odd = [], []
    for inst in plot.get("instruments") or []:
        h = inst.get("focusH")
        if h is None:
            continue                      # blank is head height, and is fine
        if h == 0:
            deck.append(inst)
        elif not low <= h <= high:
            odd.append(inst)
    out = []
    if deck:
        out.append(Finding("warning", "focus-at-the-deck",
                           f"{len(deck)} instruments are focused at height 0 — "
                           f"the deck, not head height. Blank means 5'-6\"; "
                           f"0 means the floor and is computed as the floor",
                           [_label(i) for i in deck]))
    if odd:
        out.append(Finding("warning", "focus-height-unusual",
                           f"{len(odd)} focus heights are outside "
                           f"{ph.fmt_ft(low)}–{ph.fmt_ft(high)}",
                           [f"{_label(i)} — {ph.fmt_ft(i['focusH'])}" for i in odd]))
    return out


def unfocused(plot):
    """Units still pointing straight down, which means nobody has focused them.

    ⭐ Jerry's own test for whether a show has been focused: look at the plot and
    see whether everything still points down. A unit is hung plumb because the
    electrician hanging it does not yet know where it goes.

    One finding for the plot, not one per unit — on a rep plot this is every
    unit in the house and it is not news.
    """
    plumb = [i for i in plot.get("instruments") or []
             if i.get("focusX") == i.get("x") and i.get("focusY") == i.get("y")
             and i.get("x") is not None]
    total = len(plot.get("instruments") or [])
    if not plumb:
        return []
    return [Finding("warning", "unfocused",
                    f"{len(plumb)} of {total} instruments still point straight "
                    f"down, so they have not been focused",
                    [_label(i) for i in plumb])]


def unit_numbering(plot):
    """Unit numbers outside 1..n for a position carrying n units.

    ⚠ A WARNING, DELIBERATELY. Numbering the stage-right half 1-10 and the
    stage-left half 21-30 is real practice and reads better on a hang sheet than
    a single run. What this actually catches is the leftover: a 200 among
    twenty-eight units, a 300 among fourteen, which is an import that never
    finished rather than a numbering scheme.
    """
    byp = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        n = positions.unit_key(inst.get("unit"))[0]
        if n != float("inf"):
            byp[(inst.get("position") or "").strip()].append((n, inst))
    out = []
    for pos, group in sorted(byp.items()):
        # ⭐ The NUMERIC part only, so 10A on a pipe of nineteen is in range. A
        # suffixed unit shares its number with the one it was added beside; that
        # is what the suffix is for, and counting it as a separate slot would
        # report every insertion as an error.
        over = [i for n, i in group if not 1 <= n <= len(group)]
        if over:
            out.append(Finding("warning", "unit-out-of-range",
                               f"{pos or 'no position'} carries {len(group)} "
                               f"instruments, so units run 1-{len(group)}; "
                               f"{len(over)} of them "
                               f"{'is' if len(over) == 1 else 'are'} outside "
                               f"that range",
                               [f"unit {positions.unit_label(i['unit'])}" for i
                                in sorted(over, key=lambda i:
                                          positions.unit_key(i.get("unit")))]))
    return out


def missing_channels(plot):
    """Units with no channel yet. Normal while drawing, wrong before a hookup."""
    blank = [i for i in plot.get("instruments") or [] if i.get("channel") is None]
    return [Finding("warning", "no-channel",
                    f"{len(blank)} instruments have no channel, so they appear "
                    f"on the plot and not in the hookup",
                    [_label(i) for i in blank])] if blank else []


def shared_addresses(plot):
    """One DMX address on more than one instrument.

    ⚠ NOT AN ERROR. Ganging conventionals on one dimmer is ordinary — four
    Shakespeares on a cyc circuit share an address because they are one light as
    far as the desk is concerned. On an LED fixture the same thing is almost
    always a patching slip, and the file does not say which case it is.
    """
    seen = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        if inst.get("address") is not None:
            seen[(inst.get("universe"), inst["address"])].append(inst)
    out = []
    for (uni, addr), group in sorted(seen.items(), key=lambda kv: str(kv[0])):
        if len(group) > 1:
            where = f"address {addr}" + (f" in universe {uni}" if uni else "")
            out.append(Finding("warning", "shared-address",
                               f"{len(group)} instruments are patched to {where}",
                               [_label(i) for i in group]))
    return out


def colours(plot):
    """A colour that is not a gel the table knows.

    It returns no transmission and says so, which is honest and invisible — the
    plot simply has no footcandle figure for that unit. 'NC/Temp' in the Big
    House sample is a note to the electrician, not a filter.
    """
    bad = collections.defaultdict(list)
    for inst in plot.get("instruments") or []:
        colour = str(inst.get("color") or "").strip()
        if colour and ph.gel_factor(colour)[0] is None:
            bad[colour].append(inst)
    return [Finding("warning", "not-a-gel",
                    f"{colour!r} is not in the gel table, so {len(group)} "
                    f"instruments have no transmission and no footcandles",
                    [_label(i) for i in group])
            for colour, group in sorted(bad.items())]


def trims(plot):
    """A unit at a different trim from the position it hangs on.

    Legitimate when a position is raked and the legs carry their own trims, so
    the comparison is against ALL the legs of that name, not the first one.
    """
    legs, bad = _legs(plot), []
    for inst in plot.get("instruments") or []:
        here = legs.get((inst.get("position") or "").strip().lower())
        if not here or inst.get("trim") is None:
            continue
        theirs = {p["trim"] for p in here if p.get("trim") is not None}
        if theirs and inst["trim"] not in theirs:
            bad.append((inst, sorted(theirs)))
    return [Finding("warning", "trim-mismatch",
                    f"{len(bad)} instruments are trimmed differently from the "
                    f"position they hang on",
                    [f"{_label(i)} at {ph.fmt_ft(i['trim'])}, position at "
                     f"{', '.join(ph.fmt_ft(t) for t in theirs)}"
                     for i, theirs in bad])] if bad else []


CHECKS = (duplicate_units, unknown_positions, off_the_run, unknown_types,
          focus_heights, unfocused, unit_numbering, missing_channels,
          shared_addresses, colours, trims)


def check(plot):
    """Every check, errors first. Returns a list of Findings."""
    found = []
    for fn in CHECKS:
        found.extend(fn(plot))
    return sorted(found, key=lambda f: f.level != "error")


def report(findings, show=6):
    """The findings as text. `show` units per finding, then a count."""
    if not findings:
        return "  nothing to report\n"
    out = []
    for f in findings:
        mark = "🔴" if f.level == "error" else "⚠ "
        out.append(f"  {mark} [{f.check}] {f.says}")
        for u in f.units[:show]:
            out.append(f"       · {u}")
        if len(f.units) > show:
            out.append(f"       · … and {len(f.units) - show} more")
    return "\n".join(out) + "\n"


def main(argv):
    """Check each file named. Exit 1 if any of them has an error."""
    if not argv:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    errors = 0
    for path in argv:
        with open(path, encoding="utf-8") as fh:
            plot = json.load(fh)
        findings = check(plot)
        bad = sum(1 for f in findings if f.level == "error")
        errors += bad
        warn = len(findings) - bad
        print(f"{path} — {len(plot.get('instruments') or [])} instruments, "
              f"{bad} error{'' if bad == 1 else 's'}, "
              f"{warn} warning{'' if warn == 1 else 's'}")
        print(report(findings))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
