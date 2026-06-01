"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

from pathlib import Path


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    """Build ruff-style error strings."""
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


def _write_lines(path: Path, lines: list[str]) -> None:
    """Write lines to a file with trailing newline."""
    path.write_text("\n".join(lines) + "\n")
