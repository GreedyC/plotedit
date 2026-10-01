#!/usr/bin/env python3
"""Where plots live on disk, and the only code allowed to write there.

⭐ Jerry, 2026.09.24: "the save is not automatically overwriting the file — it
tries a new name Without Consent.plot (1).json." That suffix is the browser's
DOWNLOAD behaviour. Save was written on the File System Access API, which can
overwrite a file in place — but only Chrome and Edge have it, so on Safari and
Firefox every press landed another copy in Downloads and the newest plot was
whichever had the longest number in brackets.

⚠ ONE code path, not two. A browser-API save and a server save would behave
differently on different machines, which is the divergence that has cost a day
already elsewhere in this repo. This is a tool with its own local server; the
server can write the file, so it always does.

🔴 THE NAME IS A NAME, NEVER A PATH. Everything written goes in the plots
directory and nowhere else: no separators, no "..", no absolute paths, no
symlinks followed out. The service binds to localhost and the person driving it
owns the machine, but "the user is trusted" is not a reason to accept
../../.ssh/authorized_keys from a web page.
"""
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

# A filename, and nothing that could be a path. Also rules out the empty stem,
# so ".json" — hidden on macOS and Linux — cannot be created.
SAFE_NAME = re.compile(r"^[\w][\w ()\-.]{0,120}\.json$")

# ⚠ WINDOWS DEVICE NAMES. On Windows these are not filenames at all — CON is the
# console, NUL is the bin, LPT1 is a printer port — and opening "CON.json" talks
# to the device instead of creating a file, with the extension ignored. The
# pattern above lets them through because they are ordinary words, and a
# designer typing "aux.json" for an auxiliary rig would get silence and no file.
_RESERVED = {"con", "prn", "aux", "nul",
             *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


#: Set by `set_root` when the designer picks a folder in this session.
#: ⚠ Session-only on purpose. Writing a chosen path into a config file is a
#: second place for it to live and a second thing to go stale when the folder
#: moves; PLOTEDIT_PLOTS is the setting that persists, and it is already there.
_chosen: Optional[Path] = None


def root() -> Path:
    """The plots directory. Created on first use.

    In order: a folder picked in this session, then PLOTEDIT_PLOTS, then `plots`
    beside the tool — so a designer can keep plots in Dropbox or in a show folder
    rather than inside a checkout.
    """
    if _chosen is not None:
        _chosen.mkdir(parents=True, exist_ok=True)
        return _chosen
    env = os.environ.get("PLOTEDIT_PLOTS")
    base = Path(env) if env else Path(__file__).resolve().parents[2] / "plots"
    base.mkdir(parents=True, exist_ok=True)
    return base


def set_root(path: Path) -> Path:
    """Point the plots folder somewhere else for this session.

    ⭐ THIS MOVES THE FENCE; IT DOES NOT OPEN THE GATE. `resolve` still matches
    the name against a pattern AND requires the resolved path to sit inside
    whatever `root()` now is, so a plot name still cannot escape its folder. The
    only thing that changed is which folder that is.

    ⚠ The path comes from the operating system's own dialog, chosen by the person
    at the keyboard — never from the browser. See `folderpick`.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{path} is not a folder")
    global _chosen            # pylint: disable=global-statement
    _chosen = path
    return path


def resolve(name: str) -> Path:
    """The path a plot name refers to, or ValueError saying why it does not.

    ⚠ Checked BOTH ways: the name is matched against a pattern, and then the
    resolved path is required to sit inside the plots directory. The pattern
    alone would be a promise about a regex; the containment check is a fact
    about the filesystem, and it catches the case the pattern did not think of.
    """
    if not isinstance(name, str) or not SAFE_NAME.match(name):
        raise ValueError(
            f"{name!r} is not a plot file name — letters, numbers, spaces, "
            f"() - . only, ending in .json, and no folders"
        )
    if ".." in name:
        raise ValueError(f"{name!r} is not a plot file name")
    if name.split(".")[0].strip().lower() in _RESERVED:
        raise ValueError(
            f"{name!r} is a reserved device name on Windows — "
            f"call it something else so the plot works on every machine")
    base = root()
    path = (base / name).resolve()
    if path.parent != base.resolve():
        raise ValueError(f"{name!r} would write outside the plots folder")
    return path


def listing() -> list:
    """Every plot on disk, newest first, with the show name read out of each."""
    out = []
    for p in sorted(root().glob("*.json")):
        try:
            show = json.loads(p.read_text()).get("show", "")
        except (OSError, ValueError):
            # ⚠ A file that will not parse is still LISTED, and says so. Hiding
            # it would read as "that plot is gone", which is the wrong thing to
            # believe about a file you can see in Finder.
            show = "— will not parse —"
        st = p.stat()
        out.append({"name": p.name, "show": show, "bytes": st.st_size,
                    "modified": st.st_mtime})
    out.sort(key=lambda r: r["modified"], reverse=True)
    return out


def read(name: str) -> dict:
    return json.loads(resolve(name).read_text())


def write(name: str, plot: dict) -> Path:
    """Save a plot, atomically.

    ⭐ Written to a temporary file in the same directory and then RENAMED over
    the target, so a crash or a full disk cannot leave a half-written plot where
    the whole one used to be. os.replace is atomic within a filesystem, and the
    temp file is made alongside the target to keep it on the same one.
    """
    path = resolve(name)
    body = json.dumps(plot, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".part")
    try:
        # ⚠ mkstemp creates at 0600 and os.replace keeps the source's mode, so
        # every saved plot came out readable by nobody but the owner — a
        # surprise the first time one is opened from a shared folder or copied
        # to a drive for the shop. Normal file permissions, minus the umask.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path
