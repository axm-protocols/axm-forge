"""Unit tests for MergeSquashHook author injection (AXM-1826).

No real I/O: ``resolve_identity``, ``run_git`` and ``find_git_root`` are
monkeypatched (module-level imports in ``merge_squash`` -> patch on the
consuming module).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pytest_mock import MockerFixture

from axm_git.hooks.merge_squash import MergeSquashHook

_IDENTITY = SimpleNamespace(name="Secondary", email="secondary@axm-protocol.io")
_AUTHOR_FLAG = "--author=Secondary <secondary@axm-protocol.io>"


def _git_ok(stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _context() -> dict[str, object]:
    return {
        "working_dir": "/repo",
        "session_id": "abc",
        "protocol_name": "p",
    }


def test_squash_builds_author_arg(mocker: MockerFixture) -> None:
    """AC1, AC3: resolved identity is injected as --author into the squash commit."""
    mocker.patch("axm_git.hooks.merge_squash.find_git_root", return_value=Path("/repo"))
    mocker.patch("axm_git.hooks.merge_squash.resolve_identity", return_value=_IDENTITY)
    run_git = mocker.patch(
        "axm_git.hooks.merge_squash.run_git", side_effect=lambda *a, **k: _git_ok()
    )

    result = MergeSquashHook().execute(_context())

    assert result.success is True
    commit_calls = [c for c in run_git.call_args_list if c.args[0][0] == "commit"]
    assert len(commit_calls) == 1
    commit_args = commit_calls[0].args[0]
    assert _AUTHOR_FLAG in commit_args


def test_squash_no_identity_no_author(mocker: MockerFixture) -> None:
    """AC2: no resolved identity -> no --author (falls back to default git identity)."""
    mocker.patch("axm_git.hooks.merge_squash.find_git_root", return_value=Path("/repo"))
    mocker.patch("axm_git.hooks.merge_squash.resolve_identity", return_value=None)
    run_git = mocker.patch(
        "axm_git.hooks.merge_squash.run_git", side_effect=lambda *a, **k: _git_ok()
    )

    result = MergeSquashHook().execute(_context())

    assert result.success is True
    commit_calls = [c for c in run_git.call_args_list if c.args[0][0] == "commit"]
    assert len(commit_calls) == 1
    commit_args = commit_calls[0].args[0]
    assert all("--author" not in arg for arg in commit_args)
