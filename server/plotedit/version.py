"""What build this is.

⭐ A tester who reports something has to be able to say WHICH version they saw
it in, and until now nothing in the download said. The releases are git tags, so
a clone knows its version and an unzipped release knows nothing at all — which
is backwards, because the people who need it most are the ones who never cloned.

The release workflow writes VERSION into the package from the tag. A clone has
no such file and says so rather than guessing: "dev" is the honest answer when
the code may be anything at all.

⚠ Never invent a number. A build that claims to be 0.1.7 and is not sends
somebody hunting a bug in the wrong source.
"""
from pathlib import Path

_FILE = Path(__file__).resolve().parent / "VERSION"


def version() -> str:
    """The released version, or "dev" for anything not built by the workflow."""
    try:
        v = _FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"
    return v or "dev"
