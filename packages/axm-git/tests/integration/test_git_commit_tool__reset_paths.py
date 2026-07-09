"""Scoped-restore invariant of GitCommitTool after a hook refusal.

On a definitive ``pre-commit`` refusal the tool scoped-resets *only* the paths
the operation staged (:func:`axm_git.core.runner.reset_paths`), leaving the
worktree untouched and any third-party pre-staged path intact; a green (or
autofix-then-green) hook commits normally. Every assertion reads real ``git``
output from a throwaway repo under ``tmp_path``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _staged(repo: Path) -> set[str]:
    """Paths currently in the index (``git status --porcelain`` staged col)."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in out.stdout.splitlines() if line.strip()}


def _head_files(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in out.stdout.splitlines() if line.strip()}


def _head_subject(repo: Path) -> str:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_failing_hook_unstages_op_paths_but_keeps_worktree(
    install_hook: Callable[[str], Path],
) -> None:
    """AC1: definitive refusal → op path leaves the index, file stays on disk."""
    repo = install_hook("failing")
    (repo / "feature.py").write_text("x = 1\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["feature.py"], "message": "feat: add feature"}],
    )

    assert result.success is False
    # Index cleaned of the op-staged path (guards the scoped reset).
    assert "feature.py" not in _staged(repo)
    # The worktree file survives — restore never touches the worktree.
    assert (repo / "feature.py").read_text() == "x = 1\n"


def test_failing_hook_preserves_third_party_staged(
    install_hook: Callable[[str], Path],
) -> None:
    """AC2: a file pre-staged by the test survives a scoped restore."""
    repo = install_hook("failing")
    # Third party stages its own file *before* the git_commit call.
    (repo / "third_party.py").write_text("tp = 1\n")
    subprocess.run(
        ["git", "add", "third_party.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    (repo / "op.py").write_text("op = 1\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["op.py"], "message": "feat: op"}],
    )

    assert result.success is False
    staged = _staged(repo)
    # The pre-staged third-party path is left alone (bare reset would drop it).
    assert "third_party.py" in staged
    # The op path is the only thing unstaged.
    assert "op.py" not in staged


def test_green_hook_commits_normally(
    install_hook: Callable[[str], Path],
) -> None:
    """AC3: a green hook lands the commit and clears the index."""
    repo = install_hook("green")
    (repo / "clean.py").write_text("c = 1\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["clean.py"], "message": "feat: clean"}],
    )

    assert result.success, result.error
    assert _head_subject(repo) == "feat: clean"
    assert "clean.py" in _head_files(repo)
    assert _staged(repo) == set()


def test_autofix_then_green_commits_normally(
    install_hook: Callable[[str], Path],
) -> None:
    """AC3: an auto-fix-then-green hook re-stages and lands the retried commit."""
    repo = install_hook("autofix")
    (repo / "fix_me.py").write_text("v = 1\n")

    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["fix_me.py"], "message": "feat: fix_me"}],
    )

    assert result.success, result.error
    assert _head_subject(repo) == "feat: fix_me"
    assert "fix_me.py" in _head_files(repo)
    assert _staged(repo) == set()
