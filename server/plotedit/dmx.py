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

# ⭐ KEYED BY THE SPECIFIC MODEL, NOT THE FAMILY (Jerry, 2026.09.26). A Series 1
# and a Series 2 Lustr are both "Lustr 26 EDLT" in the photometrics — same lens,
# same optics — and they do NOT have the same personality list. Keying this on
# the family would quietly answer a Series 2 question with Series 1 data, and
# the answer would look right.
#
# Source Four LED Series 2 — "ETC Source Four LED Series 2 - Datasheet.pdf",
# p.11, "DMX Input Channel Profiles". RGB and Studio are six-channel profiles in
# which channel 4 is unused; the footprint is still six.
#
# ⚠ "Plus 7" is not a profile. It is an option that adds colour-control channels
# to RGB, HSI or HSIC.
MODELS: Dict[str, Dict[str, int]] = {
    "Source Four LED Series 2": {
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
# looks obvious is the arithmetic that got HSI Plus 7 wrong by two.
UNPUBLISHED: Dict[str, set] = {
    "Source Four LED Series 2": {"RGB Plus 7", "HSIC Plus 7"},
}

# Which models a photometric family might be. The inspector offers these.
# ⚠ A family with one known model does NOT mean the fixture is that model. It
# means that is the only one whose datasheet has been read.
FAMILY_MODELS: Dict[str, list] = {
    "Lustr": ["Source Four LED Series 2"],
}

SOURCES: Dict[str, str] = {
    "Source Four LED Series 2":
        "ETC Source Four LED Series 2 datasheet, p.11 'DMX Input Channel Profiles'",
}

# ⚠ ETC's own Quick Setup called "Stage" is HSI with Plus 7 enabled, and the
# datasheet describes it as theatrical lighting with an incandescent dimming
# curve and a 3200 K white point. It is the profile a theatre is most likely to
# be on — but "most likely" is not "recorded", so this is NEVER applied
# silently. The inspector uses it to order the list, nothing more.
SUGGESTED: Dict[str, str] = {"Source Four LED Series 2": "HSI Plus 7"}


def models_for(family: Optional[str]) -> list:
    """The specific models this photometric family might be."""
    return list(FAMILY_MODELS.get(family or "", []))


def resolve_model(family: Optional[str], model: Optional[str]):
    """Which model to look profiles up in, and whether that was recorded.

    ⚠ When the plot does not say, and exactly one model is known for the
    family, that one is used — and the note SAYS it was assumed. Silence here
    would put a channel range on paperwork on the strength of a guess about
    which generation of fixture is in the rig.
    """
    if model:
        return model, None
    known = models_for(family)
    if len(known) == 1:
        return known[0], f"assuming {known[0]} — the model is not recorded"
    return None, ("the fixture model is not recorded, and personalities differ "
                  "between models")


def profiles_for(model: Optional[str]) -> Dict[str, int]:
    """Every profile with a published channel count for this model."""
    return dict(MODELS.get(model or "", {}))


def channels(model: Optional[str], profile: Optional[str]) -> Tuple[Optional[int], str]:
    """How many addresses this fixture occupies, and why that is the answer.

    Returns `(None, reason)` when it cannot be known, never a guess.
    """
    table = MODELS.get(model or "")
    if not table:
        # Not an error. A conventional fixture has no profile, and the caller
        # decides whether one address is the right assumption for it.
        return None, f"no DMX profile table for {model or 'this fixture'}"
    if not profile:
        return None, ("the DMX profile is not recorded, and the footprint "
                      f"depends on it — a {model} runs from "
                      f"{min(table.values())} to {max(table.values())} channels")
    if profile in UNPUBLISHED.get(model or "", set()):
        return None, (f"{profile} exists, but the channel count for it is not in "
                      f"the datasheet — read it off the fixture's display")
    n = table.get(profile)
    if n is None:
        return None, (f"{profile!r} is not a profile this fixture has "
                      f"({', '.join(sorted(table))})")
    return n, f"{profile}, {n} channels — {SOURCES.get(model or '', 'source not recorded')}"


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
