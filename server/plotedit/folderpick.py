"""Ask the person, in their own operating system's folder dialog, where plots go.

⭐ Jerry, 2026-10-01: "folder picking should work just like ground plan." The
instinct is right — a native dialog, not a text box — but it cannot be done the
same way, and the reason is worth writing down.

🔴 A BROWSER WILL NOT TELL A PAGE A REAL PATH. Ground plan works because the
browser hands the page a file's CONTENTS, which are then uploaded. A plots folder
is the opposite: the SERVER writes there, so it needs a path, and the web platform
deliberately refuses to supply one. Checked rather than assumed, in the running
app:

    "path" in File.prototype      False
    "fullPath" in File.prototype  False

`<input webkitdirectory>` gives file names relative to the chosen folder and never
the folder itself. `showDirectoryPicker()` gives a handle that lives inside the
browser, is Chrome-and-Edge only, and cannot be handed to a Python process.

⭐ SO THE SERVER ASKS. plotedit already runs its own process on the person's own
machine, which is the one piece of this that is not a web page — so it opens the
operating system's own folder chooser and reads the answer directly.

⚠ A SUBPROCESS, NOT TKINTER. tkinter is in the standard library and is tempting,
but Tk must own the main thread on macOS, and this would be called from a server
request thread — which hangs or crashes rather than failing. `osascript` and
PowerShell are already there, cost no dependency, and either return a path or
return nothing.

🔴 THE CLIENT NEVER SENDS A PATH. It asks the server to ask the person. So there
is no path from the browser to validate, no traversal to defend against, and the
only string that reaches the filesystem is one the person chose in their own
file dialog.
"""
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

#: Long enough for someone to find a folder, short enough that a dialog nobody
#: can see does not wedge the request for ever.
TIMEOUT_S = 180


class PickerUnavailable(RuntimeError):
    """No native folder dialog on this machine. The caller must say so."""


def _mac(initial: Path) -> Optional[str]:
    # `choose folder` is AppleScript's own dialog. POSIX path turns the
    # colon-separated HFS answer into something Python can use.
    script = (
        f'set d to POSIX file "{initial}"\n'
        'try\n'
        '  set f to choose folder with prompt "Where should plotedit keep plots?" '
        'default location d\n'
        '  POSIX path of f\n'
        'on error number -128\n'          # the person pressed Cancel
        '  return ""\n'
        'end try\n'
    )
    out = subprocess.run(["osascript", "-e", script], capture_output=True,
                         text=True, timeout=TIMEOUT_S, check=False)
    return (out.stdout or "").strip() or None


def _windows(initial: Path) -> Optional[str]:
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description = 'Where should plotedit keep plots?';"
        f"$d.SelectedPath = '{initial}';"
        "if ($d.ShowDialog() -eq 'OK') {{ $d.SelectedPath }}"
    )
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        raise PickerUnavailable("PowerShell was not found")
    out = subprocess.run([exe, "-NoProfile", "-Command", ps], capture_output=True,
                         text=True, timeout=TIMEOUT_S, check=False)
    return (out.stdout or "").strip() or None


def _linux(initial: Path) -> Optional[str]:
    # ⚠ Best effort. A desktop Linux usually has one of these; a headless one has
    # neither, and saying so is better than a dialog nobody will ever see.
    for exe, args in (("zenity", ["--file-selection", "--directory",
                                  f"--filename={initial}/"]),
                      ("kdialog", ["--getexistingdirectory", str(initial)])):
        found = shutil.which(exe)
        if not found:
            continue
        out = subprocess.run([found, *args], capture_output=True, text=True,
                             timeout=TIMEOUT_S, check=False)
        return (out.stdout or "").strip() or None
    raise PickerUnavailable("neither zenity nor kdialog is installed")


def available() -> bool:
    """Can this machine show a folder dialog at all?"""
    system = platform.system()
    if system == "Darwin":
        return shutil.which("osascript") is not None
    if system == "Windows":
        return bool(shutil.which("powershell") or shutil.which("pwsh"))
    return bool(shutil.which("zenity") or shutil.which("kdialog"))


def choose(initial: Path) -> Optional[Path]:
    """Show the dialog. Returns the chosen folder, or None if it was cancelled.

    ⚠ Raises PickerUnavailable when the machine has no dialog to show, and
    TimeoutExpired if nobody answers. Both are the caller's to report — a picker
    that silently does nothing looks like a broken button.
    """
    system = platform.system()
    pick = {"Darwin": _mac, "Windows": _windows}.get(system, _linux)
    chosen = pick(initial)
    if not chosen:
        return None
    path = Path(chosen).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{path} is not a folder")
    if not os.access(path, os.W_OK):
        raise ValueError(f"{path} cannot be written to")
    return path
