"""Unit tests for the shared git commit command builder."""

from __future__ import annotations

from axm_git.core.commit_cmd import build_commit_cmd


def test_build_commit_cmd_omits_no_verify() -> None:
    cmd = build_commit_cmd("msg", None, skip_hooks=False)
    assert "--no-verify" not in cmd


def test_build_commit_cmd_includes_no_verify() -> None:
    cmd = build_commit_cmd("msg", None, skip_hooks=True)
    assert "--no-verify" in cmd


def test_build_commit_cmd_includes_author() -> None:
    cmd = build_commit_cmd(
        "msg", None, skip_hooks=True, author="Secondary <secondary@example.com>"
    )
    assert "--author=Secondary <secondary@example.com>" in cmd


def test_build_commit_cmd_omits_author() -> None:
    cmd = build_commit_cmd("msg", None, skip_hooks=True)
    assert all(not arg.startswith("--author") for arg in cmd)
