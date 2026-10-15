"""Timeout refusals preserve candidate index and bounded hook evidence."""

import subprocess
from pathlib import Path

import pytest

import axm_git.core.commit_spec as retry_module
import axm_git.tools.commit as commit_module
from axm_git.tools.commit import GitCommitTool


@pytest.mark.parametrize("retry", [False, True])
@pytest.mark.parametrize("staged_third_party", [False, True])
def test_commit_timeout_restores_only_own_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    retry: bool,
    staged_third_party: bool,
) -> None:
    """First and retry timeouts retain prior index entries and causal evidence."""
    repo = tmp_path / "candidate"
    repo.mkdir()
    for key, value in {
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }.items():
        monkeypatch.setenv(key, value)

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=repo, text=True, capture_output=True, check=True
        ).stdout.strip()

    git("init")
    (repo / "a.txt").write_text("before\n")
    (repo / "b.txt").write_text("before\n")
    git("add", ".")
    git("commit", "-m", "test: baseline")
    head = git("rev-parse", "HEAD")
    (repo / "a.txt").write_text("candidate\n")
    files = ["a.txt"]
    if staged_third_party:
        (repo / "b.txt").write_text("third-party\n")
        git("add", "b.txt")
        files.append("b.txt")
    calls = 0
    original = commit_module.run_git

    def scripted(args: list[str], path: Path, **kwargs: object) -> object:
        nonlocal calls
        if args and args[0] == "commit":
            calls += 1
            if retry and calls == 1:
                (repo / "a.txt").write_text("autofixed\n")
                return subprocess.CompletedProcess(args, 1, "files were modified", "")
            raise subprocess.TimeoutExpired(
                ["git", *args],
                300,
                output=b"stdout-evidence" + b"x" * 20000,
                stderr=b"stderr-evidence",
            )
        return original(args, path, **kwargs)

    monkeypatch.setattr(commit_module, "run_git", scripted)
    monkeypatch.setattr(retry_module, "run_git", scripted)
    result = GitCommitTool().execute(
        path=str(repo), commits=[{"message": "fix: candidate", "files": files}]
    )
    assert not result.success
    assert git("rev-parse", "HEAD") == head
    assert git("diff", "--cached", "--name-only") == (
        "b.txt" if staged_third_party else ""
    )
    assert calls == (2 if retry else 1)
    assert result.error and "timed out" in result.error
    assert isinstance(result.data, dict)
    failed = result.data["failed_commit"]
    assert failed["index_restored"] is True
    assert failed["restored_paths"] == ["a.txt"]
    assert failed["retried"] is retry
    assert failed["auto_fixed_files"] == (["a.txt"] if retry else [])
    assert failed["cause"] == "timeout"
    assert failed["timeout_seconds"] == 300
    assert "stdout-evidence" in failed["precommit_output"]
    assert "stderr-evidence" in failed["precommit_output"]
    assert len(failed["precommit_output"]) < 17000


@pytest.mark.parametrize("restore_timeout", [False, True])
def test_timeout_restoration_failure_keeps_original_cause(
    commit_repo: Path, monkeypatch: pytest.MonkeyPatch, restore_timeout: bool
) -> None:
    """Failed index restoration is reported honestly without masking timeout."""
    from axm_git.core import runner

    (commit_repo / "README.md").write_text("candidate\n")
    original = runner.run_git

    def refuse_reset(args: list[str], root: Path, **kwargs: object) -> object:
        if args[0] == "reset":
            if restore_timeout:
                raise subprocess.TimeoutExpired(["git", *args], 30)
            return subprocess.CompletedProcess(args, 1, "", "index.lock evidence")
        return original(args, root, **kwargs)

    def timeout_commit(args: list[str], root: Path, **kwargs: object) -> object:
        if args[0] == "commit":
            raise subprocess.TimeoutExpired(["git", *args], 30, stderr="hook evidence")
        return original(args, root, **kwargs)

    monkeypatch.setattr(runner, "run_git", refuse_reset)
    monkeypatch.setattr(commit_module, "run_git", timeout_commit)
    result = GitCommitTool().execute(
        path=str(commit_repo),
        commits=[{"message": "fix: candidate", "files": ["README.md"]}],
    )
    assert not result.success
    assert isinstance(result.data, dict)
    failure = result.data["failed_commit"]
    assert failure["cause"] == "timeout"
    assert failure["index_restored"] is False
    assert failure["restored_paths"] == []
    assert failure["restore_error"]
    assert "hook evidence" in failure["precommit_output"]
    assert result.error and "timed out" in result.error
