"""E2E test: ``axm-init check`` surfaces wheel-doc-shipping failures (AXM-1715)."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_check_command_exits_nonzero_on_orphan_doc(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"

            [tool.axm-init.wheel-doc]
            files = ["docs/x.md"]

            [tool.hatch.build.targets.wheel]
            packages = ["src/pkg"]
            """
        ).lstrip()
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_text("# x\n")

    proc = subprocess.run(
        ["uv", "run", "axm-init", "check", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "pyproject.pyproject_wheel_doc_shipping" in combined
    assert "x.md" in combined


def _run_check(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke `axm-init check` with *args* and capture the outcome."""
    return subprocess.run(
        ["uv", "run", "axm-init", "check", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_workspace_category_on_standalone_prints_na(tmp_path: Path) -> None:
    """AC1/AC2: `check --category workspace` on a standalone project prints an
    N/A line (not 0/100 Grade F) and exits 0."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    proc = _run_check(str(tmp_path), "--category", "workspace")

    combined = proc.stdout + proc.stderr
    assert "not applicable" in combined or "N/A" in combined
    assert "Score: 0/100" not in combined
    assert proc.returncode == 0


def test_check_inapplicable_category_exit_code_is_zero(tmp_path: Path) -> None:
    """AC2: an inapplicable category returns exit code exactly 0."""
    proc = _run_check(str(tmp_path), "--category", "workspace")

    assert proc.returncode == 0


def test_check_failing_applicable_category_exits_one(tmp_path: Path) -> None:
    """AC3: an applicable category scoring a real 0 exits 1 with 0/100 Grade F."""
    proc = _run_check(str(tmp_path), "--category", "ci")

    combined = proc.stdout + proc.stderr
    assert "0/100" in combined
    assert "Grade F" in combined
    assert proc.returncode == 1
