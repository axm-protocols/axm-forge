"""Integration: tool and hook produce identical commit behaviour (AC4).

The same ``commit_spec`` routed through ``GitCommitTool.execute`` and
``CommitPhaseHook.commit_from_outputs`` (both delegating to the shared core
helpers) must yield an identical staged/committed tree and the same author.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.commit_phase import CommitPhaseHook
from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=root, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=root, check=True)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _seed_repo(root: Path) -> str:
    """Init a repo with one commit; return the resulting HEAD sha."""
    _init_repo(root)
    (root / "seed.txt").write_text("seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init", "--no-verify")
    return _git(root, "rev-parse", "HEAD")


def _write_hook(repo: Path, script: str) -> None:
    """Install *script* as the repo's executable ``pre-commit`` hook."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(script)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# First invocation rewrites the staged file and exits non-zero with the autofix
# marker; on the retry it lands the commit itself (nested ``--no-verify``) yet
# still exits non-zero — modelling a runner that commits but reports failure
# (the AXM-22 root cause).
_SELF_COMMIT_HOOK = (
    "#!/bin/sh\n"
    'gd="$(git rev-parse --git-dir)"\n'
    'if [ ! -f "$gd/autofix-done" ]; then\n'
    '  : > "$gd/autofix-done"\n'
    "  printf 'autofixed\\n' >> target.py\n"
    '  echo "files were modified by this hook"\n'
    "  exit 1\n"
    "fi\n"
    "unset GIT_INDEX_FILE\n"
    'git commit --no-verify -m "landed by hook" >"$gd/nested.log" 2>&1\n'
    "exit 1\n"
)

# Rejects every commit and never auto-fixes (no marker) — a genuine failure.
_ALWAYS_FAIL_HOOK = "#!/bin/sh\necho 'hook rejected the commit' >&2\nexit 1\n"

# Rewrites the staged file and emits the marker on every attempt — never settles.
_ALWAYS_AUTOFIX_HOOK = (
    "#!/bin/sh\n"
    "printf 'autofixed\\n' >> target.py\n"
    'echo "files were modified by this hook"\n'
    "exit 1\n"
)


def test_tool_and_hook_produce_same_tree(tmp_path: Path) -> None:
    """AC4: same commit_spec via tool and hook -> identical tree + author."""
    spec = {"message": "feat: add file", "files": ["f.txt"]}

    tool_repo = tmp_path / "tool"
    tool_repo.mkdir()
    _init_repo(tool_repo)
    (tool_repo / "f.txt").write_text("hello\n")
    tool_result = GitCommitTool().execute(path=str(tool_repo), commits=[dict(spec)])
    assert tool_result.success, tool_result.error

    hook_repo = tmp_path / "hook"
    hook_repo.mkdir()
    _init_repo(hook_repo)
    (hook_repo / "f.txt").write_text("hello\n")
    hook_result = CommitPhaseHook().execute(
        {"commit_spec": dict(spec)},
        from_outputs=True,
        working_dir=str(hook_repo),
    )
    assert hook_result.success, hook_result

    tool_tree = _git(tool_repo, "rev-parse", "HEAD^{tree}")
    hook_tree = _git(hook_repo, "rev-parse", "HEAD^{tree}")
    assert tool_tree == hook_tree

    tool_author = _git(tool_repo, "log", "-1", "--format=%an <%ae>")
    hook_author = _git(hook_repo, "log", "-1", "--format=%an <%ae>")
    assert tool_author == hook_author


def test_tool_reports_success_when_hook_lands_commit_but_exits_nonzero(
    tmp_path: Path,
) -> None:
    """AXM-22 (tool): a re-stage+retry lands the commit yet git exits non-zero.

    GitCommitTool must trust the real repository state and report success.
    """
    before = _seed_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _write_hook(tmp_path, _SELF_COMMIT_HOOK)

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["target.py"], "message": "feat: add target"}],
    )

    assert result.success is True, result.error
    assert _git(tmp_path, "rev-parse", "HEAD") != before
    assert _git(tmp_path, "status", "--porcelain") == ""
    record = result.data["results"][0]
    assert record["retried"] is True
    assert record["sha"] == _git(tmp_path, "rev-parse", "HEAD")[:7]


def test_hook_reports_success_when_hook_lands_commit_but_exits_nonzero(
    tmp_path: Path,
) -> None:
    """AXM-22 mirror (hook): commit_from_outputs trusts the real repo state."""
    before = _seed_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _write_hook(tmp_path, _SELF_COMMIT_HOOK)

    result = CommitPhaseHook().execute(
        {"commit_spec": {"files": ["target.py"], "message": "feat: add target"}},
        from_outputs=True,
        working_dir=str(tmp_path),
    )

    assert result.success is True, result
    assert _git(tmp_path, "rev-parse", "HEAD") != before
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_tool_fails_when_hook_rejects_without_autofix(tmp_path: Path) -> None:
    """A permanent hook failure (no autofix marker) stays a real failure."""
    before = _seed_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _write_hook(tmp_path, _ALWAYS_FAIL_HOOK)

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["target.py"], "message": "feat: add target"}],
    )

    assert result.success is False
    assert result.data["failed_commit"]["retried"] is False
    assert _git(tmp_path, "rev-parse", "HEAD") == before


def test_hook_fails_when_hook_rejects_without_autofix(tmp_path: Path) -> None:
    """CommitPhaseHook mirror: a permanent hook failure stays success=False."""
    before = _seed_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _write_hook(tmp_path, _ALWAYS_FAIL_HOOK)

    result = CommitPhaseHook().execute(
        {"commit_spec": {"files": ["target.py"], "message": "feat: add target"}},
        from_outputs=True,
        working_dir=str(tmp_path),
    )

    assert result.success is False
    assert _git(tmp_path, "rev-parse", "HEAD") == before


def test_tool_fails_when_nothing_to_commit(tmp_path: Path) -> None:
    """Nothing to commit stays success=False with no phantom commit."""
    _init_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init", "--no-verify")
    before = _git(tmp_path, "rev-parse", "HEAD")

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["target.py"], "message": "feat: unchanged"}],
    )

    assert result.success is False
    assert _git(tmp_path, "rev-parse", "HEAD") == before


def test_tool_single_retry_no_false_green_when_hook_never_settles(
    tmp_path: Path,
) -> None:
    """A hook that modifies files on every attempt: one retry, no false green."""
    before = _seed_repo(tmp_path)
    (tmp_path / "target.py").write_text("x = 1\n")
    _write_hook(tmp_path, _ALWAYS_AUTOFIX_HOOK)

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["target.py"], "message": "feat: add target"}],
    )

    assert result.success is False
    assert result.data["failed_commit"]["retried"] is True
    assert _git(tmp_path, "rev-parse", "HEAD") == before
