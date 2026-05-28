"""Shared helpers for ``tests/integration``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.integration._helpers import <name>``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


_PLAN_CHECK = "axm_audit.core.fix.stages_plan._check_by_rule"


def _anvil_available() -> bool:
    try:
        from axm_audit.core.fix.layout_and_move import move_symbols
    except ImportError:
        return False
    return move_symbols is not None


def _mk_pkg(tmp_path: Path, name: str = "pkg") -> Path:
    pkg_dir = tmp_path / "src" / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("")
    return pkg_dir


def _subprocess_import(target: Path, pkg: Path) -> subprocess.CompletedProcess[str]:
    """Import *target* via a fresh subprocess; PYTHONPATH set to pkg/src."""
    env = {**os.environ, "PYTHONPATH": str(pkg / "src")}
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import importlib.util, sys; "
            "spec = importlib.util.spec_from_file_location('m', sys.argv[1]); "
            "m = importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(m)",
            str(target),
        ],
        cwd=pkg,
        env=env,
        capture_output=True,
        text=True,
    )
