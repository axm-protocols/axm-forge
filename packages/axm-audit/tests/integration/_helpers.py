"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import Any

_PYPROJECT = (
    textwrap.dedent(
        """
    [project]
    name = "mypkg"
    version = "0"
    """
    ).strip()
    + "\n"
)


def _find_pair(
    clusters: list[dict[str, Any]], names: set[str]
) -> dict[str, Any] | None:
    for c in clusters:
        cluster_names = {t["name"] for t in c["members"]}
        if names.issubset(cluster_names):
            return c
    return None


def _make_minimal_project(root: Path) -> None:
    src = root / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "module.py").write_text("x = 1\n")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.1"\n')


def _make_src_module__from_coupling_severity(
    tmp_path: Path,
    pkg: str,
    module: str,
    n_imports: int,
) -> None:
    """Create a source module that imports *n_imports* stdlib modules."""
    src = tmp_path / "src" / pkg
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")

    stdlib_modules = [
        "os",
        "sys",
        "json",
        "re",
        "math",
        "io",
        "csv",
        "ast",
        "copy",
        "time",
        "uuid",
        "enum",
        "types",
        "shutil",
        "string",
        "random",
        "hashlib",
        "logging",
        "pathlib",
        "textwrap",
        "functools",
        "itertools",
        "collections",
        "contextlib",
        "dataclasses",
        "operator",
        "struct",
        "socket",
        "signal",
        "threading",
        "subprocess",
    ]
    lines = [f"import {m}" for m in stdlib_modules[:n_imports]]
    lines.append("\nx = 1\n")
    (src / f"{module}.py").write_text("\n".join(lines), encoding="utf-8")


def _tools_available() -> bool:
    """Check that ruff and mypy are on PATH."""
    return shutil.which("ruff") is not None and shutil.which("mypy") is not None
