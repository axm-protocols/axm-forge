"""Shared AST helpers for rule implementations."""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["get_python_files", "parse_file_safe"]


def get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory recursively."""
    if not directory.exists():
        return []
    return list(directory.rglob("*.py"))


def parse_file_safe(path: Path) -> ast.Module | None:
    """Parse a Python file, returning None on error."""
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None
