"""Integration test: run_git completes within timeout on a real repo."""

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
