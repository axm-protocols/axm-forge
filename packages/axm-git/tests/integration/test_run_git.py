"""Integration test: run_git completes within timeout on a real repo.

Also merged from ``test_runner.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.core.runner import run_git

pytestmark = pytest.mark.integration


def test_run_git_completes_within_timeout_on_real_repo(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init"], cwd=tmp_path, check=True, capture_output=True, timeout=30
    )
    result = run_git(["status", "--short"], cwd=tmp_path)
    assert result.returncode == 0


class TestRunGit:
    """Test run_git helper."""

    def test_success(self, tmp_path: Path) -> None:
        run_git(["init"], tmp_path)
        result = run_git(["status", "--short"], tmp_path)
        assert result.returncode == 0

    def test_failure_bad_dir(self, tmp_path: Path) -> None:
        result = run_git(["status"], tmp_path)
        assert result.returncode != 0

    def test_defaults(self, tmp_path: Path) -> None:
        """Verify default kwargs are applied."""
        run_git(["init"], tmp_path)
        result = run_git(["status"], tmp_path)
        # text=True → stdout is str
        assert isinstance(result.stdout, str)
