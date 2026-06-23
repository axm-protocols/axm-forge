"""Home directory resolution and in-repo path guard.

``axm_home()`` returns the resolved ``~/.axm`` directory, creating it with
mode ``0700`` (idempotent, tightening looser pre-existing perms). ``resolve_safe``
is the security primitive the vault relies on: it refuses any path that resolves
inside a git repository / source checkout, so a ``0600`` secrets/config file can
never land in a repo.

Pure stdlib only (``pathlib``, ``os``, ``stat``); no third-party import.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["AXM_DIR_MODE", "axm_home", "resolve_safe"]

AXM_DIR_MODE = 0o700


def axm_home() -> Path:
    """Return the resolved ``~/.axm`` directory, creating it ``0700`` if absent.

    Idempotent: a pre-existing directory with looser permissions is tightened
    back to ``0700``. Permission calls degrade gracefully on non-POSIX systems.
    """
    home = (Path.home() / ".axm").resolve()
    home.mkdir(mode=AXM_DIR_MODE, parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(home, AXM_DIR_MODE)
    return home


def resolve_safe(target: Path | str) -> Path:
    """Resolve ``target`` and refuse any path sitting inside a git repo.

    Walks the resolved path and its ancestors looking for a ``.git`` marker
    (a source checkout). Raises :class:`ValueError` rather than returning an
    in-repo path; returns the resolved path otherwise.
    """
    resolved = Path(target).resolve()
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / ".git").exists():
            msg = (
                f"refusing in-repo path {resolved}: "
                f"resolves inside the git checkout at {ancestor}"
            )
            raise ValueError(msg)
    return resolved
