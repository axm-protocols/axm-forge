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


@pytest.mark.parametrize(
    ("src_body", "test_path", "test_body"),
    [
        pytest.param(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            "tests/unit/test_sample.py",
            """
            from sample import add

            def test_add() -> None:
                assert add(2, 3) == 5
            """,
            id="clean_project",
        ),
        pytest.param(
            "def hello() -> str:\n    return 'hi'\n",
            "tests/unit/test_via_cli.py",
            """
            import subprocess

            def test_runs_a_subprocess() -> None:
                result = subprocess.run(
                    ["echo", "hi"], capture_output=True, text=True, check=False
                )
                assert result.returncode == 0
            """,
            id="plumbing_subprocess_in_unit_dir",
        ),
    ],
)
def test_pyramid_findings_unchanged(
    tmp_path: Path, src_body: str, test_path: str, test_body: str
) -> None:
    """Legitimate test layouts produce no pyramid mismatches."""
    (tmp_path / "src" / "sample").mkdir(parents=True)
    (tmp_path / "src" / "sample" / "__init__.py").write_text(src_body)
    test_file = tmp_path / test_path
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(dedent(test_body).lstrip())
    _write_pyproject(tmp_path)

    payload = _run_test_quality(tmp_path)
    mismatches = payload.get("pyramid_mismatches", [])
    assert mismatches == [], (
        f"legitimate layout should not produce pyramid mismatches; "
        f"got payload: {payload}"
    )
