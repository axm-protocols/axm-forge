"""Resolution of the project's configured ruff ``line-length``.

Thin ``services/`` module in the shape of :mod:`axm_edit.services.lint`: it
reads the project's configuration and answers a single question — how wide a
line the project actually allows. Strictly read-only.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from axm_edit.utils import resolve_safe

__all__ = ["DEFAULT_LINE_LENGTH", "parse_line_length", "resolve_line_length"]

#: Ruff's built-in default, and the limit ``batch_edit`` lints against.
DEFAULT_LINE_LENGTH = 88

_PYPROJECT = "pyproject.toml"


def parse_line_length(pyproject_text: str) -> int | None:
    """Extract ``[tool.ruff] line-length`` from an in-memory TOML text.

    Args:
        pyproject_text: Full ``pyproject.toml`` content, already read.

    Returns:
        The declared integer, or ``None`` when the key is absent (or the
        text is not valid TOML).
    """
    try:
        data = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError:
        return None

    ruff = data.get("tool", {}).get("ruff", {})
    if not isinstance(ruff, dict):
        return None

    value = ruff.get("line-length")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def resolve_line_length(root: Path) -> int:
    """Return the ``line-length`` configured under *root*.

    Args:
        root: Project root the batch is applied to.

    Returns:
        The value declared in ``root/pyproject.toml``, or
        :data:`DEFAULT_LINE_LENGTH` when no readable declaration is found.
    """
    pyproject = resolve_safe(root, _PYPROJECT)
    if pyproject is None or not pyproject.is_file():
        return DEFAULT_LINE_LENGTH

    try:
        text = pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return DEFAULT_LINE_LENGTH

    parsed = parse_line_length(text)
    return DEFAULT_LINE_LENGTH if parsed is None else parsed
