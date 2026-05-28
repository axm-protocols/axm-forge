"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

from pathlib import Path


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def _write_empty_new(root: Path) -> Path:
    new = root / "src" / "pkg" / "new.py"
    new.write_text("")
    return new


def _write_old_foo(root: Path) -> Path:
    old = root / "src" / "pkg" / "old.py"
    old.write_text("def Foo():\n    return 1\n")
    return old


def _write_pyproject__from_move_cycle_detection(
    root: Path, name: str = "mypkg"
) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
    )
