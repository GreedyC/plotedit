"""Circuits on a hanging position.

⭐ THE CONSTRAINT, in Jerry's words (2026.09.23):

    "Circuits depend on the house — no set order."

**So this module never invents a circuit number, and never infers one from
position.** Unit numbers follow a rule and can be generated; circuits do not and
cannot. A house wired its pipes years ago in whatever order made sense to the
electrician who did it, and the only source of truth is that house: its rep
plot, its circuit map, or its master electrician standing under the pipe.

What this module does instead is **record what the house says and check the plot
against it.** A circuit that came from a guess is worse than a blank cell,
because a blank cell gets asked about at the site visit and a guess does not.

`circuits` on a position is therefore an INVENTORY, in the order the house has
them along the pipe if that is known. Each entry may carry a location; where the
locations are known a unit can be matched to the nearest one, and where they are
not, matching REFUSES rather than pairing them off in order — pairing in order
is exactly the guess this file exists to prevent.
"""
from typing import Any, Dict, List, Optional, Tuple


def _norm(pos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The position's circuits as dicts, however they were written.

    A house list arrives as bare numbers ([1, 2, 3]) as often as as records, and
    both are legitimate — the bare list just has no locations.
    """
    out = []
    for c in pos.get("circuits") or []:
        if isinstance(c, dict):
            out.append(dict(c))
        else:
            out.append({"id": c})
    return out


def available(pos: Dict[str, Any]) -> List[Any]:
    """The circuit ids on this position, in the house's own order."""
    return [c.get("id") for c in _norm(pos)]


def source(pos: Dict[str, Any]) -> str:
    """Where the circuit list came from. Unsourced is reported as such.

    RP-2 has nothing to say here: this is house data, and house data without a
    provenance is a rumour. `/venue` asks for the rep plot for exactly this.
    """
    return (pos.get("circuitSource") or "").strip() or "NOT RECORDED — ask the house"


def check(instruments: List[Dict[str, Any]], positions: List[Dict[str, Any]],
          control: str = "dimmer-per-circuit") -> List[str]:
    """Check the plot's circuits against what each house position actually has.

    `control` is the HOUSE's control model, per RP-2 §6.14.1 — see
    symbols.CONTROL_MODELS. Jerry, 2026.09.23: "most houses have circuit per
    dimmer," so that is the default. In such a house **the circuit and the dimmer
    are one fact, not two**, and a plot that gives them different numbers is
    describing a patch that does not exist.

    Returns plain-English problems, worst first. An empty list means every
    circuit used is one the house told us about — NOT that the plot is right,
    because a position with no recorded circuits cannot contradict anything.
    """
    problems: List[str] = []
    by_name = {(p.get("name") or "").strip().lower(): p for p in positions or []}

    unsourced = [p.get("name") for p in positions or []
                 if p.get("circuits") and not (p.get("circuitSource") or "").strip()]
    if unsourced:
        problems.append(
            "circuit list has no source on: " + ", ".join(str(n) for n in unsourced)
            + " — a circuit list without a provenance is a rumour; ask for the rep plot")

    if control == "dimmer-per-circuit":
        # ⚠ The whole point of a dimmer-per-circuit house: the circuit IS the
        # dimmer. Two different numbers means somebody has recorded a patch that
        # the building does not have, and it will be read as one at load-in.
        for i in instruments or []:
            c, d = i.get("circuit"), i.get("dimmer")
            if c not in (None, "") and d not in (None, "") and str(c) != str(d):
                problems.append(
                    f"unit {i.get('unit')}: circuit {c} but dimmer {d}. This house "
                    f"is dimmer-per-circuit, so those are one number — either the "
                    f"house has a patch and the control model is wrong, or one of "
                    f"the two is a typo")

    # ⭐ The same class of contradiction one house along. Where dimmer-per-circuit
    # says the circuit and the dimmer are one number, dimmer-is-address says the
    # DIMMER and the ADDRESS are — so a unit carrying both, differing, has
    # recorded a patch this house does not have.
    #
    # ⚠ Compared on the bare number. An address is universe-qualified ("1/45")
    # and a dimmer never is, so "45" and "1/45" are the SAME fact written two
    # ways and must not be reported as a disagreement.
    if control == "dimmer-is-address":
        for i in instruments or []:
            d, a = i.get("dimmer"), i.get("address")
            if d in (None, "") or a in (None, ""):
                continue
            bare = str(a).split("/")[-1].strip()
            if str(d).strip() != bare:
                problems.append(
                    f"unit {i.get('unit')}: dimmer {d} but address {a}. This house "
                    f"is dimmer-is-address, so those are one number — clear the "
                    f"dimmer and let the address carry it, or fix whichever is wrong")

    used: Dict[Tuple[str, Any], List[Any]] = {}
    labels: Dict[str, str] = {}
    for i in instruments or []:
        circ = i.get("circuit")
        if circ in (None, ""):
            continue
        pname = (i.get("position") or "").strip().lower()
        used.setdefault((pname, circ), []).append(i.get("unit"))
        labels[pname] = i.get("position") or pname
        pos = by_name.get(pname)
        if pos is None:
            problems.append(f"unit {i.get('unit')} is on position "
                            f"{i.get('position')!r}, which is not in the plot")
        elif pos.get("circuits"):
            if circ not in available(pos):
                problems.append(
                    f"unit {i.get('unit')} on {pos.get('name')} uses circuit {circ}, "
                    f"which the house does not list there "
                    f"(has: {', '.join(str(c) for c in available(pos))})")

    # Two units on one circuit is a twofer — legal, common, and a LOAD question,
    # so it is reported as a fact to check rather than as an error.
    for (pname, circ), units in sorted(used.items(), key=lambda kv: str(kv[0])):
        if len(units) > 1:
            problems.append(
                f"circuit {circ} on {labels.get(pname) or pname or '?'} carries units "
                f"{', '.join(str(u) for u in units)} — a twofer. Legal, but the "
                f"load is the sum; have Art check it against the house's rating")

    # A position with no circuits recorded is not an error, but it IS the reason
    # a load table cannot be produced, so say so once.
    blank = [p.get("name") for p in positions or [] if not p.get("circuits")]
    if blank:
        problems.append(
            "no circuits recorded on: " + ", ".join(str(n) for n in blank)
            + " — not an error, but no load table can be built for them")
    return problems


def match_to_units(instruments: List[Dict[str, Any]], pos: Dict[str, Any]
                   ) -> Tuple[int, List[str]]:
    """Assign each unit on `pos` the nearest circuit, IF the house gave locations.

    Returns (assigned, notes). **Refuses when locations are unknown** — pairing a
    circuit list against units in order would look like a result and be a guess,
    and a plot patched to the wrong circuits reads as correct right up until half
    the rig does not come on.

    ⚠ Nearest-circuit matching can put two units on one circuit, and there are
    routinely more units on a pipe than circuits under it. That is a legal
    twofer and a LOAD question, so every doubling it creates is reported. A
    matcher that silently doubles up is worse than one that refuses: the refusal
    gets dealt with, the silent twofer gets discovered by a breaker.
    """
    circs = _norm(pos)
    if not circs:
        return 0, [f"{pos.get('name')!r} has no circuits recorded — ask the house"]
    located = [c for c in circs if c.get("x") is not None or c.get("y") is not None]
    if len(located) != len(circs):
        return 0, [f"{pos.get('name')!r} lists circuits but not where they are on "
                   f"the pipe, so they cannot be matched to units. Circuits depend "
                   f"on the house and have no set order — assign them by hand, or "
                   f"get the circuit map."]

    from . import positions as P
    on = P.order(instruments, pos)
    lateral = P.axis(pos) == "lateral"
    notes: List[str] = []
    if len(on) > len(located):
        notes.append(f"{pos.get('name')} has {len(on)} units and only "
                     f"{len(located)} circuits — some MUST double up")
    landed: Dict[Any, List[Any]] = {}
    for inst in on:
        here = inst.get("x", 0.0) if lateral else inst.get("y", 0.0)
        best = min(located, key=lambda c: abs((c.get("x") if lateral else c.get("y")) - here))
        inst["circuit"] = best.get("id")
        landed.setdefault(best.get("id"), []).append(inst.get("unit"))
    for cid, units in landed.items():
        if len(units) > 1:
            notes.append(f"circuit {cid} now carries units "
                         f"{', '.join(str(u) for u in units)} — a twofer. Check the "
                         f"load against the house's rating before this is patched")
    return len(on), notes


def load(instruments: List[Dict[str, Any]], positions: List[Dict[str, Any]],
         control: str = "dimmer-per-circuit",
         dimmer_watts: Optional[float] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Watts per circuit, and what that means for the dimmer behind it.

    ⭐ In a dimmer-per-circuit house the circuit and the dimmer are one thing, so
    **the load on a circuit IS the load on a dimmer** and there is no patch to
    hide behind. That is the arithmetic that matters: the 2026.09 fault was a
    dimmer pack carrying more than it could, and it was fixed by adding a pack.

    `dimmer_watts` is the HOUSE's per-dimmer rating. **It is not assumed.** 2400W
    is the common 20-amp figure and it is also wrong in plenty of buildings, and
    a capacity check against a number nobody confirmed is worse than no check —
    it reads as a pass. Without it, loads are reported and nothing is judged.

    Returns (rows, notes). Each row: circuit, position, units, watts, and, when a
    rating was given, headroom as a percentage.
    """
    from . import photometrics as ph

    by_circ: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    notes: List[str] = []
    missing: List[Any] = []
    seen_notes: set = set()

    for i in instruments or []:
        circ = i.get("circuit")
        if circ in (None, ""):
            continue
        key = ((i.get("position") or "").strip(), circ)
        row = by_circ.setdefault(key, {"circuit": circ, "position": i.get("position"),
                                       "units": [], "watts": 0.0})
        row["units"].append(i.get("unit"))
        w = i.get("wattage")
        note = None
        if w in (None, ""):
            # ph.watts_for knows the two rules: a tungsten unit's watts belong to
            # its LAMP (defaulting to HPL 575 — "S4s are 575 unless noted"), and
            # an LED's belong to its ENGINE and its OUTPUT MODE.
            w, note = ph.watts_for(i.get("type"), i.get("lamp"), i.get("mode"))
            if note and "TYPICAL IS NOT PEAK" in note and "typical" not in seen_notes:
                seen_notes.add("typical")
                notes.append("LED figures are the published TYPICAL draw, not peak — for a "
                             "capacity check, compute the highest mode the rig can be run in")
        if w in (None, ""):
            missing.append(i.get("unit"))
            w = 0.0
        row["watts"] += float(w)

    rows = sorted(by_circ.values(), key=lambda r: (str(r["position"]), str(r["circuit"])))

    if missing:
        notes.append(f"no wattage for units {', '.join(str(u) for u in missing)} — "
                     f"they count as ZERO, so these totals are a floor, not a total")
    if dimmer_watts is None:
        notes.append("no per-dimmer rating given, so nothing is judged — ask the "
                     "house for its dimmer rating rather than assuming 2400W")
    else:
        for r in rows:
            r["headroom_pct"] = round(100.0 * (1 - r["watts"] / dimmer_watts), 1)
            if r["watts"] > dimmer_watts:
                notes.append(f"circuit {r['circuit']} on {r['position']} is OVER: "
                             f"{r['watts']:.0f}W on a {dimmer_watts:.0f}W dimmer")
            elif r["headroom_pct"] < 20:
                notes.append(f"circuit {r['circuit']} on {r['position']} is at "
                             f"{r['watts']:.0f}W — {r['headroom_pct']:.0f}% headroom")
    if control == "dimmer-per-circuit" and rows:
        notes.append("dimmer-per-circuit house: these ARE the dimmer loads. "
                     "The pack total is the next question — see /load-in")
    return rows, notes
