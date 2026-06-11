"""Integration: tool and hook produce identical commit behaviour (AC4).

The same ``commit_spec`` routed through ``GitCommitTool.execute`` and
``CommitPhaseHook.commit_from_outputs`` (both delegating to the shared core
helpers) must yield an identical staged/committed tree and the same author.
"""

from __future__ import annotations

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
