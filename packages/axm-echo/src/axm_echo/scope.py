"""Scope loader for the echo corpus.

Reads the optional ``~/axm/echo.toml`` config to decide which workspace
roots the corpus extractor walks. Self-contained: only ``tomllib`` +
``pathlib``, zero external dependency (AC5).

Graceful degradation is the hard contract: a missing file, a missing
``workspace_roots`` key, or a malformed TOML never raises -- it falls
back to the current working directory as the single root. There is **no**
upward disk auto-discovery.

NOTE (rule of three): a future ``axm-config`` package may own this
loading once a third consumer appears. Until then we deliberately avoid
coupling to an unbuilt package and keep the loader local.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

__all__ = ["config_path", "load_scope"]

_CONFIG_RELATIVE = Path("axm") / "echo.toml"


def config_path() -> Path:
    """Return the path to the echo config (``~/axm/echo.toml``).

    Does not check existence; callers degrade gracefully when absent.
    """
    return Path.home() / _CONFIG_RELATIVE


def load_scope() -> list[Path]:
    """Return the workspace roots to scan, with graceful degradation.

    Reads ``workspace_roots`` from ``~/axm/echo.toml`` when present and
    well-formed. On any failure (file absent, unreadable, invalid TOML,
    missing or empty ``workspace_roots``) returns ``[Path.cwd()]`` so the
    caller still has the current workspace to scan -- never an exception.

    Returns:
        Resolved, de-duplicated workspace root paths. Always non-empty.
    """
    roots = _read_configured_roots()
    if not roots:
        return [Path.cwd().resolve()]
    return roots


def _read_configured_roots() -> list[Path]:
    """Parse ``workspace_roots`` from the config, or return ``[]``."""
    path = config_path()
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []

    declared = data.get("workspace_roots")
    if not isinstance(declared, list):
        return []

    seen: set[Path] = set()
    roots: list[Path] = []
    for entry in declared:
        if not isinstance(entry, str):
            continue
        resolved = Path(entry).expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots
