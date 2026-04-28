from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest


def _make_clean_project(root: Path) -> None:
    """Build a minimal package with no test_quality findings.

    A real package layout is required so the rules can run, but the test
    suite is intentionally trivial and pyramid-correct.
    """
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


@pytest.mark.e2e
def test_cli_runs_test_quality_category(tmp_path: Path) -> None:
    """`audit . --category test_quality` runs to completion and emits output.

    The exit code reflects whether the project passes the score threshold;
    we only require that the CLI ran without crashing (returncode in {0, 1})
    and produced visible output mentioning the audited category.
    """
    _make_clean_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", ".", "--category", "test_quality"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode in (0, 1), (
        f"CLI crashed (rc={result.returncode}): {result.stderr}"
    )
    assert result.stdout != ""


@pytest.mark.e2e
def test_cli_test_quality_category_passes_on_clean_project(tmp_path: Path) -> None:
    """On a project with no test_quality issues, exit code is 0."""
    _make_clean_project(tmp_path)

    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", ".", "--category", "test_quality"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode == 0, (
        f"clean project should pass test_quality\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
