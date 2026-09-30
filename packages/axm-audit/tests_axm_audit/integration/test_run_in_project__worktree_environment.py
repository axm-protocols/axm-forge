"""Validation uses a source venv and candidate code without uv path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from axm_audit.core.runner import run_in_project

pytestmark = pytest.mark.integration


@pytest.fixture
def candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = tmp_path / "source"
    gitdir = source / ".git" / "worktrees" / "candidate"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..")
    (source / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    lane = tmp_path / "lane"
    (lane / "src" / "lane_sample").mkdir(parents=True)
    (lane / ".git").write_text(f"gitdir: {gitdir}")
    (lane / "src" / "lane_sample" / "__init__.py").write_text("VALUE = 'candidate'\n")
    (source / "src" / "lane_sample").mkdir(parents=True)
    (source / "src" / "lane_sample" / "__init__.py").write_text("VALUE = 'source'\n")
    monkeypatch.setenv("PYTHONPATH", str(source / "src"))
    (lane / "pyproject.toml").write_text(
        '[project]\nname = "lane-sample"\nversion = "0.1.0"\n'
        'dependencies = ["missing-editable"]\n'
        "[tool.uv.sources]\n"
        'missing-editable = {path = "../does-not-exist", editable = true}\n'
    )
    (lane / "test_candidate.py").write_text(
        "from lane_sample import VALUE\ndef test_candidate():\n"
        "    assert VALUE == 'candidate'\n"
    )
    return lane


def test_broken_relative_dependency_does_not_trigger_uv_sync(candidate: Path) -> None:
    result = run_in_project(
        ["pytest", "-q", "--no-cov", "test_candidate.py"],
        candidate,
        capture_output=True,
        text=True,
        with_packages=["pytest-cov", "pytest-json-report"],
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert not (candidate / ".venv").exists()
    assert not (candidate / "uv.lock").exists()


@pytest.mark.parametrize("instrument", ["ruff", "mypy"])
def test_lane_runs_validation_instruments(candidate: Path, instrument: str) -> None:
    result = run_in_project(
        [instrument, "--version"], candidate, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert instrument in result.stdout
