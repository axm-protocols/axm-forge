"""Integration tests for GitPRTool against a real git repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.tools.pr import GitPRTool

pytestmark = pytest.mark.integration


def _init_repo(root: Path) -> None:
    run_git(["init", "-b", "main"], root)
    run_git(["config", "user.email", "test@test.com"], root)
    run_git(["config", "user.name", "Test"], root)
    (root / "f.txt").write_text("x\n")
    run_git(["add", "."], root)
    run_git(["commit", "-m", "init"], root)


def test_git_pr_explicit_base_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: an explicit base wins over the resolved repo default."""
    _init_repo(tmp_path)
    captured: dict[str, list[str]] = {}

    def _fake_run_gh(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="https://github.com/o/r/pull/1",
            stderr="",
        )

    monkeypatch.setattr("axm_git.tools.pr.gh_available", lambda: True)
    monkeypatch.setattr("axm_git.tools.pr.run_gh", _fake_run_gh)

    result = GitPRTool().execute(
        title="t", base="develop", auto_merge=False, path=str(tmp_path)
    )

    assert result.success
    create_args = captured["args"]
    assert "--base" in create_args
    assert create_args[create_args.index("--base") + 1] == "develop"


def test_git_pr_on_non_git_dir_fails(tmp_path: Path) -> None:
    """Failure path: creating a PR outside a repo returns a readable error."""
    result = GitPRTool().execute(title="t", path=str(tmp_path))
    assert not result.success
    assert result.error
