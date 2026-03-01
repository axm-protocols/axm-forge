"""Shared utilities for audit check modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _load_toml(project: Path) -> dict[str, Any] | None:
    """Load pyproject.toml, return None if missing/corrupt."""
    path = project / "pyproject.toml"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return None
