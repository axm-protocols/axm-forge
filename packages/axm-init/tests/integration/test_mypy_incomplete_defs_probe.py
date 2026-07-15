"""Guard probe: the package mypy config must relax partial annotations under
``tests/`` while still flagging them under ``src/``.

This pins the ``[[tool.mypy.overrides]] module = ["tests.*"]`` relaxation so a
silent config drift (dropping the override, or leaking strictness into tests)
fails loudly. The probe writes a canonical partially-annotated function
(``def probe_partial(fixture) -> None: ...``) into the real package tree so that
mypy resolves the module path (``tests.*`` vs ``axm_init.*``) exactly as it does
in production, then removes every artifact in a ``finally`` block so the
worktree stays pristine on pass or fail.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

__all__ = ["has_untyped_def_error"]

# tests/integration/<this file> -> package root is two levels up.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
TESTS_DIR = PACKAGE_ROOT / "tests" / "integration"
SRC_DIR = PACKAGE_ROOT / "src" / "axm_init"

# Return annotation present, parameter unannotated -> incomplete def.
PROBE_CONTENT = "def probe_partial(fixture) -> None:\n    ...\n"


def has_untyped_def_error(output: str) -> bool:
    """True when mypy output signals an untyped/incomplete function def."""
    return "no-untyped-def" in output or "missing a type annotation" in output


def _run_mypy(target: Path) -> subprocess.CompletedProcess[str]:
    """Run mypy on ``target`` using the package's own pyproject config."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(PYPROJECT),
            str(target),
        ],
        cwd=str(PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
def test_partial_annotation_under_tests_passes() -> None:
    target = TESTS_DIR / f"_mypy_probe_ok_{os.getpid()}.py"
    target.write_text(PROBE_CONTENT)
    try:
        result = _run_mypy(target)
    finally:
        target.unlink(missing_ok=True)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert not has_untyped_def_error(combined), combined


@pytest.mark.integration
def test_same_content_under_src_is_flagged() -> None:
    target = SRC_DIR / f"_mypy_probe_bad_{os.getpid()}.py"
    target.write_text(PROBE_CONTENT)
    try:
        result = _run_mypy(target)
    finally:
        target.unlink(missing_ok=True)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert has_untyped_def_error(combined), combined


@pytest.mark.integration
def test_probe_removes_all_temp_artifacts() -> None:
    targets = [
        TESTS_DIR / f"_mypy_probe_clean_{os.getpid()}.py",
        SRC_DIR / f"_mypy_probe_clean_{os.getpid()}.py",
    ]
    for target in targets:
        target.write_text(PROBE_CONTENT)
        try:
            _run_mypy(target)
        finally:
            target.unlink(missing_ok=True)

    assert all(not target.exists() for target in targets)
