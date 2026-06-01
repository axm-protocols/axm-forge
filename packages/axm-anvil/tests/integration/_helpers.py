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


SOURCE_WITH_METHOD = (
    '"""Source module."""\n\n\n'
    "def real_toplevel() -> int:\n"
    "    return 42\n\n\n"
    "class TestBasicThing:\n"
    "    def test_basic(self) -> None:\n"
    "        assert True\n"
)


def _write_workspace(root: Path) -> None:
    """Lay out a two-member uv workspace (pkg_a, pkg_b) under ``root``."""
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/pkg_a", "packages/pkg_b"]\n'
    )
    for name in ("pkg_a", "pkg_b"):
        member = root / "packages" / name
        pkg = member / "src" / name
        pkg.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        )
        (pkg / "__init__.py").write_text("")
