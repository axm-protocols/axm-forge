"""Integration tests for the `test-quality` CLI subcommand.

These tests run the CLI against controlled fixture projects (not the repo
itself) so they don't break when the audited codebase legitimately changes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest


def _make_minimal_project(root: Path) -> None:
    """Create a minimal pyramid-correct project with no tautological tests."""
    (root / "src" / "sample").mkdir(parents=True)
    (root / "src" / "sample" / "__init__.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_sample.py").write_text(
        dedent(
            """
            from sample import add

            def test_add() -> None:
                assert add(2, 3) == 5
            """
        ).lstrip()
    )
    (root / "pyproject.toml").write_text(
        dedent(
            """
            [project]
            name = "sample"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        ).lstrip()
    )


@pytest.mark.integration
def test_test_quality_cli_emits_valid_json(tmp_path: Path) -> None:
    """`test-quality --json` emits parseable JSON regardless of pass/fail."""
    _make_minimal_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in (0, 1), (
        f"CLI crashed (rc={result.returncode}): {result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict | list)


@pytest.mark.integration
def test_test_quality_cli_clean_project_no_findings(tmp_path: Path) -> None:
    """On a clean project, no tautology verdicts are emitted."""
    _make_minimal_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    verdicts = payload.get("verdicts", []) if isinstance(payload, dict) else payload
    assert verdicts == [], f"clean project unexpectedly produced verdicts: {verdicts}"


@pytest.mark.integration
def test_test_quality_cli_detects_tautology(tmp_path: Path) -> None:
    """`test-quality` flags an obvious tautology when present."""
    (tmp_path / "src" / "sample").mkdir(parents=True)
    (tmp_path / "src" / "sample" / "__init__.py").write_text("x = 1\n")
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_taut.py").write_text(
        dedent(
            """
            def test_obvious_tautology() -> None:
                assert True
            """
        ).lstrip()
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
    )

    result = subprocess.run(
        ["uv", "run", "axm-audit", "test-quality", ".", "--json"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in (0, 1)
    payload = json.loads(result.stdout)
    verdicts = payload.get("verdicts", []) if isinstance(payload, dict) else payload
    trivially_true = [
        v
        for v in verdicts
        if isinstance(v, dict) and v.get("pattern") == "trivially_true"
    ]
    assert trivially_true, (
        f"`assert True` should have produced a trivially_true verdict; got: {payload}"
    )
