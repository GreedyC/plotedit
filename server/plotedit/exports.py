#!/usr/bin/env python3
"""Everything that leaves the editor.

    plot_pdf(plot, path)        architectural-scale PDF, scale bar, 1-inch check
    plot_dxf(plot, path)        layered DXF in feet
    schedule_csv(plot)          by position and unit — what gets hung
    hookup_csv(plot)            by channel — what the board sees
    eos_patch(plot)             USITT ASCII patch  ⚠ UNVERIFIED, see below
    magic_sheet_rows(plot)      channel, purpose, color, grouped

⚠ THE EOS PATCH FORMAT HAS NEVER BEEN TESTED AGAINST A CONSOLE.

The cue exporter in eos_ascii.py was reverse-engineered from a real Eos export
after three guesses at the format failed — the lesson being that a real file out
of the target application settles in minutes what documentation does not. No
real Eos *patch* export was available when this was written, so the layout below
follows the USITT spec and nothing more. **Import it into a scratch show file
before relying on it**, and if it is wrong, export a patch from Eos and diff.
The file says so in its own header, so nobody is misled downstream.
"""
import csv
import io
import re
from typing import Any, Dict, List

from . import photometrics as ph
from . import dmx


# --------------------------------------------------------------- helpers

def _sorted_for_schedule(instruments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """By position, then unit — the order someone hangs in."""
    return sorted(instruments, key=lambda i: (str(i.get("position") or "~"),
                                              _num(i.get("unit"))))


def _sorted_for_hookup(instruments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """By channel — the order the board sees. Unpatched units go last."""
    return sorted(instruments, key=lambda i: (i.get("channel") is None,
                                              _num(i.get("channel"))))


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("inf")


def _csv(rows: List[List[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerows(rows)
    return buf.getvalue()


# --------------------------------------------------------------- paperwork

# ⭐ "Thru" sits beside Address rather than folding the range into one cell, so
# the sheet still sorts and filters on a plain start address. It is blank for a
# one-address fixture and blank when the footprint is unknown — never a guess.
SCHEDULE_COLUMNS = ["Position", "Unit", "Channel", "Circuit", "Dimmer", "Address",
                    "Thru", "Type", "Wattage", "Color", "Gobo", "Purpose",
                    "Accessory", "Notes"]


def _accessories(inst) -> str:
    """The accessory cell. A list on the instrument, one cell on the schedule.

    Joined with " + " rather than a comma: the schedule is a CSV and the shop
    reads this column as a line on the order, so a comma inside a cell is a
    quoting problem waiting to be somebody's missing barn door.
    """
    a = inst.get("accessories")
    if a is None:                     # tolerate the old single-string field
        a = inst.get("accessory") or []
    if isinstance(a, str):
        a = [a] if a else []
    return " + ".join(str(x) for x in a if str(x).strip())


def _watts(inst: Dict[str, Any]) -> tuple:
    """(watts, why) for one instrument, for the load columns.

    ⭐ Jerry, 2026.09.24: "let's add the load (wattage) to the instrument
    schedule and channel report." The schedule has HAD a Wattage column all
    along — it read `inst["wattage"]`, a field nothing ever fills, so every row
    came out blank while photometrics.watts_for() knew the answer.

    ⚠ An explicit wattage on the instrument WINS. It is the only way to say
    "this one has a 750 in it" about a fixture whose family says 575, and a
    computed figure that overrode it would quietly contradict the plot, where a
    750 is drawn with a blackened rear.

    ⚠ Unknown is NEVER zero. A blank cell in a load column is read as "nothing
    on that circuit", which is the one wrong answer that matters: it is how a
    dimmer gets loaded past its rating on paper and trips in the room.
    """
    own = inst.get("wattage")
    if own not in (None, ""):
        try:
            return float(own), "on the instrument"
        except (TypeError, ValueError):
            return None, f"{own!r} is not a wattage"
    return ph.watts_for(inst.get("type", ""), inst.get("lamp"), inst.get("mode"))


def _watt_cell(w) -> str:
    """How a wattage prints. UNKNOWN says so, in words a reader cannot skim
    past as an empty cell."""
    return "UNKNOWN" if w is None else f"{w:g}"


def _load_total(instruments: List[Dict[str, Any]]) -> List[List[Any]]:
    """The total row, and the truth about how complete it is.

    ⚠ A total printed beside unknown units is a total of SOME of them, and a
    reader comparing it to a dimmer rating has no way to tell. It says how many
    it could not count, every time.
    """
    known = [w for w, _ in (_watts(i) for i in instruments) if w is not None]
    missing = len(instruments) - len(known)
    total = sum(known)
    rows: List[List[Any]] = [[], [f"TOTAL LOAD", f"{total:g} W",
                                  f"{len(known)} of {len(instruments)} units"]]
    if missing:
        rows.append(["", "", f"⚠ {missing} unit{'s' if missing > 1 else ''} "
                             f"{'have' if missing > 1 else 'has'} no wattage on file "
                             f"— this total is INCOMPLETE"])
    return rows


def _patch_cells(i: Dict[str, Any]) -> tuple:
    """(address, thru) for a sheet with two columns.

    ⭐ Through `dmx.patch_cell`, the same call the inspector and the on-screen
    schedule make. ⚠ `thru` is blank when the footprint is not known, never a
    guess — a Thru an electrician cannot rely on is worse than an empty cell,
    because an empty cell makes them ask.
    """
    text, _why, n = dmx.patch_cell(ph.FIXTURES.get(i.get("type")), i.get("type"),
                                   i.get("address"), i.get("dimmer"),
                                   i.get("model"), i.get("profile"))
    addr = i.get("address") or ""
    if not addr or n in (None, 1):
        return addr, ""
    return addr, (dmx.end_address(addr, n) or "")


def schedule_csv(plot: Dict[str, Any]) -> str:
    """The instrument schedule: what hangs where, in hanging order."""
    rows: List[List[Any]] = [[f"{plot.get('show', '')} — Instrument Schedule"],
                             [plot.get("venue", "")],
                             [f"Design: {plot.get('designer', '')}",
                              plot.get("date", ""), f"Rev {plot.get('revision', '')}"],
                             [], SCHEDULE_COLUMNS]
    for i in _sorted_for_schedule(plot["instruments"]):
        rows.append([i.get("position", ""), i.get("unit", ""), i.get("channel", ""),
                     i.get("circuit", ""), i.get("dimmer", ""), *_patch_cells(i),
                     i.get("type", ""),
                     _watt_cell(_watts(i)[0]), i.get("color", ""), i.get("gobo", ""),
                     i.get("purpose", ""), _accessories(i), i.get("notes", "")])
    rows += _load_total(plot["instruments"])
    return _csv(rows)


HOOKUP_COLUMNS = ["Channel", "Position", "Unit", "Type", "Watts", "Color",
                  "Purpose", "Circuit", "Dimmer", "Address", "Thru"]


def hookup_csv(plot: Dict[str, Any]) -> str:
    """The channel hookup: what the board sees, in channel order."""
    rows: List[List[Any]] = [[f"{plot.get('show', '')} — Channel Hookup"],
                             [plot.get("venue", "")],
                             [f"Design: {plot.get('designer', '')}",
                              plot.get("date", ""), f"Rev {plot.get('revision', '')}"],
                             [], HOOKUP_COLUMNS]
    for i in _sorted_for_hookup(plot["instruments"]):
        rows.append([i.get("channel", ""), i.get("position", ""), i.get("unit", ""),
                     i.get("type", ""), _watt_cell(_watts(i)[0]),
                     i.get("color", ""), i.get("purpose", ""),
                     i.get("circuit", ""), i.get("dimmer", ""), *_patch_cells(i)])
    rows += _load_total(plot["instruments"])
    return _csv(rows)


def magic_sheet_rows(plot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Channels grouped by purpose — the one page looked at during tech."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for i in _sorted_for_hookup(plot["instruments"]):
        groups.setdefault(str(i.get("purpose") or "unassigned"), []).append(i)
    out = []
    for purpose, insts in groups.items():
        chans = [i["channel"] for i in insts if i.get("channel") is not None]
        colors = sorted({str(i.get("color")) for i in insts if i.get("color")})
        out.append({"purpose": purpose, "channels": chans,
                    "count": len(insts), "colors": colors,
                    "types": sorted({str(i.get("type")) for i in insts if i.get("type")})})
    return out


# --------------------------------------------------------------- console

_ADDRESS = re.compile(r"^\s*(\d+)\s*[/.]\s*(\d+)\s*$|^\s*(\d+)\s*$")


def _addr_text(addr):
    """An address as Eos writes it: a bare number, or universe/address.

    ⚠ "2/45" is not 2 divided by 45 and it is not 245. A console that takes
    universes needs the slash carried through, so the string is normalised
    rather than turned into an int and back.
    """
    m = _ADDRESS.match(str(addr))
    # ⚠ Only ever called for an address _unpatchable() has already accepted.
    # Saying so out loud rather than assuming it: an unguarded .group() on None
    # is the same class of crash this whole change exists to remove.
    if m is None:
        raise ValueError(f"not an address: {addr!r}")
    if m.group(3) is not None:
        return str(int(m.group(3)))
    return f"{int(m.group(1))}/{int(m.group(2))}"


def _filled(v):
    """A field somebody actually put a value in."""
    return v is not None and str(v).strip() != ""


def _patch_target(i):
    """What this unit patches to and where the number came from, or the reason
    it cannot be patched at all: `(text, source)` or `(None, why)`.

    ⭐ AN ADDRESS AND A DIMMER ARE ALTERNATIVES, NOT A PAIR (Jerry, 2026.09.26).
    A conventional unit in a dimmer-per-circuit house has a dimmer and no DMX
    address of its own; an LED unit has an address and no dimmer. Either one is
    a complete answer to "what does this channel talk to", and demanding both
    would refuse most real plots. USITT ASCII agrees — the classic Patch entry
    is channel<dimmer.

    ⚠ The source travels back with the number so the file can say which units
    were patched from a dimmer. A dimmer number is only the DMX address when
    the racks are addressed one-to-one, which is usual and is not guaranteed,
    and an assumption that big does not belong buried in a column.
    """
    addr, dim = i.get("address"), i.get("dimmer")
    if _filled(addr) and _ADDRESS.match(str(addr)):
        return _addr_text(addr), "address"
    if _filled(dim) and _ADDRESS.match(str(dim)):
        return _addr_text(dim), "dimmer"
    if _filled(addr):
        return None, "address is not a number or universe/address"
    if _filled(dim):
        return None, f"dimmer is not a number ({dim!r})"
    return None, "no address and no dimmer"


def _unpatchable(ch, addr, dimmer=None):
    """Why this unit cannot be patched, or None if it can.

    🔴 IT USED TO CRASH. The address was passed straight to int(), so a plot
    that recorded an honest "PENDING — universe 2" — which is the right thing
    to write when the address is not known yet — took the whole export down
    with a ValueError. The file is a draft for a console; a unit whose address
    nobody has decided belongs in the NOT PATCHED list beside the ones with no
    address at all, not in a traceback.
    """
    if ch is None:
        return "no channel"
    try:
        int(ch)
    except (TypeError, ValueError):
        return f"channel is not a number ({ch!r})"
    text, why = _patch_target({"address": addr, "dimmer": dimmer})
    return None if text is not None else why


def _partition(plot: Dict[str, Any]):
    """Split the instruments into the patchable and the not.

    ⭐ ONE place. The exporter and the check that refuses an empty file both
    read from here, so they cannot disagree about the count — a refusal that
    fires when the file would not have been empty is its own kind of wrong.
    """
    patched, skipped = [], []
    for i in plot["instruments"]:
        why = _unpatchable(i.get("channel"), i.get("address"), i.get("dimmer"))
        if why:
            skipped.append((i, why))
        else:
            text, source = _patch_target(i)
            patched.append((int(i["channel"]), text, i, source))
    return patched, skipped


def eos_patch_refusal(plot: Dict[str, Any]):
    """Why this plot cannot make a patch file at all, or None if it can.

    🔴 IT USED TO EXPORT NOTHING, QUIETLY. A plot whose rig has not been
    addressed yet produced a valid file with an empty `Patch 1` block. Eos
    imports it without a murmur and patches nothing, and the reason — every
    unit listed as NOT PATCHED — sits in a comment at the top of a file nobody
    opens. An evening went into deciding the ASCII format was wrong before
    anyone opened the file and found it was simply empty.

    A crash at least tells you something happened. This said nothing at all,
    which is the worst failure this program has. So it refuses now, and says
    why, in front of the user.
    """
    patched, skipped = _partition(plot)
    if patched:
        return None
    if not skipped:
        return "there are no instruments on this plot to patch."
    n = len(skipped)
    neither = sum(1 for _, why in skipped if why == "no address and no dimmer")
    detail = (f"{neither} of them have neither an address nor a dimmer"
              if neither else "none of them can be patched")
    return (f"the patch would be empty — {detail}, out of {n} "
            f"instrument{'s' if n != 1 else ''}. Eos imports an empty patch "
            f"without complaining and patches nothing, so this is refused "
            f"rather than exported. Give the units an address or a dimmer "
            f"— either one is enough — and try again.")


def eos_patch(plot: Dict[str, Any]) -> str:
    """USITT ASCII patch: channel < address.

    ⚠ UNVERIFIED — see the module docstring. The warning is written into the
    file itself so it travels with it.

    Units with no channel or no address are listed as comments rather than
    dropped, because a silently missing unit at tech is worse than a noisy file.
    """
    show = plot.get("show", "Untitled")
    L = ["Ident 3:0", "Manufacturer ETC", "Console Eos", "$$Format 3.10",
         f"$$Title {show}", "!",
         "! PATCH ONLY. Import as MERGE so existing cues survive.",
         "!",
         "! ⚠ THIS FORMAT HAS NOT BEEN TESTED AGAINST A CONSOLE.",
         "!   The cue exporter was reverse-engineered from a real Eos export;",
         "!   no real patch export was available when this was written. Load it",
         "!   into a scratch show file first. If it is wrong, export a patch",
         "!   from Eos and diff — that settles it in minutes.",
         "!"]

    patched, skipped = _partition(plot)

    if skipped:
        L.append("! Not patched:")
        for i, why in skipped:
            L.append(f"!   {i.get('position', '?')} unit {i.get('unit', '?')} "
                     f"{i.get('type', '?')} ch={i.get('channel')} "
                     f"addr={i.get('address')} — {why}")
        L.append("!")

    from_dimmer = sorted(ch for ch, _, _, src in patched if src == "dimmer")
    if from_dimmer:
        # ⚠ Say it in the file. A dimmer number is the DMX address only when the
        # racks are addressed one-to-one — usual, not guaranteed — and whoever
        # loads this into a console is the person who can check.
        L.append("! Patched from the DIMMER, there being no address on these:")
        L.append("!   channels " + ", ".join(str(c) for c in from_dimmer))
        L.append("!   That is the classic USITT channel<dimmer entry, and it is")
        L.append("!   the DMX address only if the racks are addressed 1:1.")
        L.append("!")

    L.append("Patch 1")
    for ch, addr, _, _ in sorted(patched, key=lambda r: r[0]):
        L.append(f"   {ch}<{addr}")
    L.append(" ")

    # Channel labels carry the purpose through to the board, which is the whole
    # value of exporting a patch rather than typing it.
    for ch, _, i, _ in sorted(patched, key=lambda r: r[0]):
        label = i.get("purpose") or i.get("type") or ""
        if label:
            L.append(f"$ChanLabel {ch} {label}")
    L.append("Enddata")
    return "\n".join(L)


# --------------------------------------------------------------- drawings

def plot_pdf(plot: Dict[str, Any], pdf_path: str, dxf_path: str = None, **kw):
    """Delegates to plot_to_pdf.render, which both the PDF and the browser use."""
    import json
    import os
    import tempfile
    from plot_to_pdf import render
    fd, tmp = tempfile.mkstemp(suffix=".plot.json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(plot, fh)
        return render(tmp, pdf_path, dxf=dxf_path, **kw)
    finally:
        os.unlink(tmp)
