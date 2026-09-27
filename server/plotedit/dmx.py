"""How many DMX addresses a fixture occupies, and the range it therefore covers.

**⚠ THERE IS NO SINGLE FOOTPRINT FOR A FIXTURE TYPE.** A Source Four LED Series 2
is a six-channel fixture in HSI, a ten-channel fixture in Direct, and a fifteen-
channel fixture in HSI with Plus 7 enabled. The number depends on how the unit is
set at the back of the fixture, so the PLOT has to record the profile; the type
alone cannot answer the question.

That is why this is a table of profiles rather than a number per fixture, and why
an unrecorded profile returns None instead of a guess. A range printed on
paperwork looks exactly as authoritative whether it is right or wrong, and the
unit patched into the tail of a wrong range is the one nobody finds until tech.

⭐ EVERY ENTRY CITES THE DOCUMENT IT CAME FROM, as the photometrics do. A channel
count with no source is a rumour.

⭐ A CONVENTIONAL FIXTURE IS ONE ADDRESS. A Source Four on a dimmer occupies the
single address of that dimmer — there is no profile and nothing to look up. That
is the default, and it is right for most of any plot.
"""
from typing import Dict, Optional, Tuple

# Keyed by the `family` recorded in photometrics.FIXTURES, then by profile name.
#
# Source Four LED Series 2 — "ETC Source Four LED Series 2 - Datasheet.pdf",
# p.11, "DMX Input Channel Profiles". RGB and Studio are six-channel profiles in
# which channel 4 is unused; the footprint is still six.
#
# ⚠ "Plus 7" is not a profile. It is an option that adds seven colour-control
# channels to RGB, HSI or HSIC — the datasheet's own worked example is HSI with
# Plus 7 becoming a fifteen-channel profile.
PROFILES: Dict[str, Dict[str, int]] = {
    "Lustr": {
        "Direct": 10,
        "HSIC": 7,
        "HSI": 6,
        "RGB": 6,
        "Studio": 6,
        # 🔴 THE DATASHEET'S OWN WORKED EXAMPLE, and it is not 6 + 7. Enabling
        # Plus 7 on HSI gives a FIFTEEN channel profile: the six HSI channels,
        # then a spare at 7, the Plus 7 on/off control at 8, and the seven
        # native colours at 9-15. The first draft of this table computed 6 + 7
        # = 13 from the prose and was wrong by two.
        "HSI Plus 7": 15,
    },
}

# Profiles that exist but whose channel count the datasheet does not publish.
# ⚠ These are NOT absent from the fixture — Plus 7 is offered on RGB and HSIC
# too. The datasheet simply works only the HSI example, and the arithmetic that
# looks obvious is the arithmetic that got HSI Plus 7 wrong by two. So they
# return "not known" rather than a number nobody printed.
UNPUBLISHED: Dict[str, set] = {
    "Lustr": {"RGB Plus 7", "HSIC Plus 7"},
}

SOURCES: Dict[str, str] = {
    "Lustr": "ETC Source Four LED Series 2 datasheet, p.11 "
             "'DMX Input Channel Profiles'",
}

# ⚠ ETC's own Quick Setup called "Stage" is HSI with Plus 7 enabled, and the
# datasheet describes it as theatrical lighting with an incandescent dimming
# curve and a 3200 K white point. It is the profile a theatre is most likely to
# be on — but "most likely" is not "recorded", so this is NEVER applied
# silently. It exists so the UI can offer a sensible starting choice.
SUGGESTED: Dict[str, str] = {"Lustr": "HSI Plus 7"}


def profiles_for(family: Optional[str]) -> Dict[str, int]:
    """Every profile known for this fixture family, or {} if none are."""
    return dict(PROFILES.get(family or "", {}))


def channels(family: Optional[str], profile: Optional[str]) -> Tuple[Optional[int], str]:
    """How many addresses this fixture occupies, and why that is the answer.

    Returns `(None, reason)` when it cannot be known, never a guess.
    """
    table = PROFILES.get(family or "")
    if not table:
        # Not an error. A conventional fixture has no profile, and the caller
        # decides whether one address is the right assumption for it.
        return None, f"no DMX profile table for {family or 'this fixture'}"
    if not profile:
        return None, ("the DMX profile is not recorded, and the footprint "
                      f"depends on it — {family} runs from "
                      f"{min(table.values())} to {max(table.values())} channels")
    if profile in UNPUBLISHED.get(family or "", set()):
        return None, (f"{profile} exists, but the channel count for it is not in "
                      f"the datasheet — read it off the fixture's display")
    n = table.get(profile)
    if n is None:
        return None, (f"{profile!r} is not a profile this fixture has "
                      f"({', '.join(sorted(table))})")
    return n, f"{profile}, {n} channels — {SOURCES.get(family or '', 'source not recorded')}"


def _parts(addr: str):
    """Split "2/21" into (2, 21), or a plain "45" into (None, 45)."""
    t = str(addr).strip()
    if "/" in t:
        u, _, a = t.partition("/")
        return int(u.strip()), int(a.strip())
    return None, int(t)


def span(address, n: Optional[int]) -> Optional[str]:
    """The range this fixture covers, written the way the address was written.

    "2/21" over 15 channels is "2/21-2/35". A plain 45 over 15 is "45-59".

    ⚠ IT DOES NOT CROSS A UNIVERSE. 512 is the boundary and a fixture that ran
    past it would be describing addresses that do not exist; that returns None
    with nothing invented, because the real answer is that the patch is wrong
    and a person needs to look at it.
    """
    if not n or n < 1:
        return None
    try:
        uni, start = _parts(address)
    except (TypeError, ValueError):
        return None
    if start < 1:
        return None
    end = start + n - 1
    if end > 512:
        return None
    if n == 1:
        return f"{uni}/{start}" if uni is not None else str(start)
    if uni is not None:
        return f"{uni}/{start}-{uni}/{end}"
    return f"{start}-{end}"
