"""Integration tests for pyramid-level classification via the CLI.

Uses controlled fixture projects rather than auditing the repo itself,
so the suite doesn't break when the audited codebase legitimately changes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _run_test_quality(project: Path) -> dict[str, Any]:
    """Run `axm-audit test-quality --json` on a project and parse the payload."""
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "axm_audit",
            "test-quality",
            str(project),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(project),
        check=False,
    )
    assert result.stdout, (
        f"axm-audit produced no JSON output\n"
        f"stderr:\n{result.stderr}\nrc={result.returncode}"
    )
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def _write_pyproject(root: Path, name: str = "sample") -> None:
    (root / "pyproject.toml").write_text(
        dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        ).lstrip()
    )


def test_clean_project_yields_no_pyramid_mismatches(tmp_path: Path) -> None:
    """A project with all tests at the correct pyramid level reports zero mismatches."""
    (tmp_path / "src" / "sample").mkdir(parents=True)
    (tmp_path / "src" / "sample" / "__init__.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_sample.py").write_text(
        dedent(
            """
            from sample import add

            def test_add() -> None:
                assert add(2, 3) == 5
            """
        ).lstrip()
    )
    _write_pyproject(tmp_path)

    payload = _run_test_quality(tmp_path)
    mismatches = payload.get("pyramid_mismatches", [])
    assert mismatches == [], (
        f"clean project should not produce pyramid mismatches: {mismatches}"
    )


def test_subprocess_test_in_unit_dir_is_flagged(tmp_path: Path) -> None:
    """A subprocess-using test under tests/unit/ is flagged as misplaced.

    Should be e2e.
    """
    (tmp_path / "src" / "sample").mkdir(parents=True)
    (tmp_path / "src" / "sample" / "__init__.py").write_text(
        "def hello() -> str:\n    return 'hi'\n"
    )
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_via_cli.py").write_text(
        dedent(
            """
            import subprocess

            def test_runs_a_subprocess() -> None:
                result = subprocess.run(
                    ["echo", "hi"], capture_output=True, text=True, check=False
                )
                assert result.returncode == 0
            """
        ).lstrip()
    )
    _write_pyproject(tmp_path)

    payload = _run_test_quality(tmp_path)
    mismatches = payload.get("pyramid_mismatches", [])
    assert mismatches, (
        f"subprocess in tests/unit/ should be flagged as a pyramid mismatch; "
        f"got payload: {payload}"
    )
