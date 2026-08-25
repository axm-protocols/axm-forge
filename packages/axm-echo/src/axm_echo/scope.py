"""Scope loader for the echo corpus.

Reads the ``workspace_roots`` echo setting from the shared
``~/.axm/config.toml`` ``[echo]`` section via :mod:`axm_config` (the single
source of truth, ``env > file > default``). echo is the first real consumer of
axm-config: the hand-rolled per-file TOML loader is gone -- echo only keeps the
resolve + de-duplicate + filter post-processing on top of the raw value.

Graceful degradation is the hard contract, unchanged from the legacy loader: a
missing section, a missing/empty/ill-typed ``workspace_roots`` value, or any
axm-config failure never raises -- it falls back to the current working
directory as the single root. There is **no** upward disk auto-discovery.

The env layer round-trips too: ``AXM_ECHO_WORKSPACE_ROOTS`` arrives as a raw
string (axm-config returns env values verbatim), so it is split on
``os.pathsep`` before resolution.
"""

from __future__ import annotations

import os
from pathlib import Path

import axm_config

__all__ = ["load_scope"]

_NAMESPACE = "echo"
_KEY = "workspace_roots"
# axm-config's env-var convention for the [echo] workspace_roots key.
_ENV_VAR = "AXM_ECHO_WORKSPACE_ROOTS"


def load_scope() -> list[Path]:
    """Return the workspace roots to scan, with graceful degradation.

    Resolves ``workspace_roots`` from the shared ``~/.axm/config.toml``
    ``[echo]`` section through :func:`axm_config.get`. On any failure (absent
    section, missing/empty/ill-typed value, or an axm-config error) returns
    ``[Path.cwd().resolve()]`` so the caller still has the current workspace to
    scan -- never an exception.

    Returns:
        Resolved, de-duplicated workspace root paths. Always non-empty.
    """
    roots = _read_configured_roots()
    if not roots:
        return [Path.cwd().resolve()]
    return roots


def _read_configured_roots() -> list[Path]:
    """Resolve ``workspace_roots`` via axm-config, or return ``[]``.

    Accepts a TOML list of strings (file layer) or an ``os.pathsep``-separated
    string (env layer, ``AXM_ECHO_WORKSPACE_ROOTS``). Non-string list entries
    are skipped; any axm-config error degrades to ``[]``.
    """
    try:
        raw = axm_config.get(_NAMESPACE, _KEY, default=None)
    except Exception:  # noqa: BLE001 -- never propagate config errors to callers
        return []

    declared = _coerce_to_entries(raw)
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


def _coerce_to_entries(raw: object) -> list[object]:
    """Normalise the raw config value into a list of candidate entries.

    The file layer returns a list (TOML array) -- the only well-formed shape,
    matching the legacy contract (a non-list file value degrades to cwd). The
    env layer returns a raw ``str``; only when ``AXM_ECHO_WORKSPACE_ROOTS`` is
    actually set is a string split on ``os.pathsep`` (dropping empties).
    Anything else (``None``, a file-layer scalar/mapping) yields ``[]`` so the
    caller degrades to cwd.
    """
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str) and os.environ.get(_ENV_VAR):
        return [part for part in raw.split(os.pathsep) if part]
    return []
