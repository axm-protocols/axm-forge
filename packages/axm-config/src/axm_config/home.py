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

__all__ = [
    "AXM_DIR_MODE",
    "axm_data_path",
    "axm_home",
    "axm_home_path",
    "axm_state_path",
    "relocate_runtime_path",
    "resolve_safe",
]

AXM_DIR_MODE = 0o700


def axm_home_path() -> Path:
    """Return AXM_ROOT, or the resolved legacy ~/.axm, without creating it.

    Pure computation, the read-only counterpart of :func:`axm_home`: it never
    creates the directory nor tightens its permissions. An explicitly configured
    root must be absolute and outside a source checkout. AXM_HOME retains its
    existing configuration-override semantics; AXM_ROOT selects the installation.
    """
    configured = os.environ.get("AXM_ROOT")
    if configured is not None:
        if not configured.strip():
            raise ValueError("AXM_ROOT must name an absolute directory")
        target = Path(configured).expanduser()
        if not target.is_absolute():
            raise ValueError("AXM_ROOT must name an absolute directory")
        return resolve_safe(target)
    return (Path.home() / ".axm").resolve()


def axm_home() -> Path:
    """Return the resolved ``~/.axm`` directory, creating it ``0700`` if absent.

    Idempotent: a pre-existing directory with looser permissions is tightened
    back to ``0700``. Permission calls degrade gracefully on non-POSIX systems.
    """
    home = axm_home_path()
    home.mkdir(mode=AXM_DIR_MODE, parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(home, AXM_DIR_MODE)
    return home


def axm_state_path(*parts: str) -> Path:
    """Return service state below AXM_ROOT/state, or the legacy home by default."""
    root = axm_home_path()
    if "AXM_ROOT" in os.environ:
        root = root / "state"
    return root.joinpath(*parts)


def axm_data_path(*parts: str) -> Path:
    """Return persistent data below AXM_ROOT/data, or ~/axm by default."""
    root = axm_home_path() / "data" if "AXM_ROOT" in os.environ else Path.home() / "axm"
    return root.joinpath(*parts)


def relocate_runtime_path(value: str | os.PathLike[str]) -> Path:
    """Resolve stored legacy locations without rewriting historical records."""
    path = Path(value).expanduser()
    if "AXM_ROOT" not in os.environ or not path.is_absolute():
        return path
    path = path.resolve()
    home = Path.home().resolve()
    root = axm_home_path()
    if path == home / ".axm/config.toml":
        return root / "config.toml"
    prefixes = (
        (home / ".axm/profiles", root / "profiles"),
        (home / ".axm", root / "state"),
        (home / "axm", root / "data"),
    )
    for previous, current in prefixes:
        if path.is_relative_to(previous):
            return current / path.relative_to(previous)
    return path


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
