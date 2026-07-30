"""Unit tests for worktree_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

import pytest

from axm_git.tools.worktree_text import (
    render_add_text,
    render_failure_text,
    render_list_text,
    render_remove_text,
)


class TestRenderListText:
    """render_list_text: list sub-mode."""

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            pytest.param(
                {
                    "worktrees": [
                        {
                            "path": "/repo",
                            "HEAD": "abc1234def5678abc1234def5678abc1234def56",
                            "branch": "refs/heads/main",
                        },
                        {
                            "path": "/repo-feat",
                            "HEAD": "fed4321cba8765fed4321cba8765fed4321cba87",
                            "branch": "refs/heads/feat/x",
                        },
                    ]
                },
                (
                    "git_worktree | ✓ | list · 2 worktrees\n"
                    "/repo abc1234 main\n"
                    "/repo-feat fed4321 feat/x"
                ),
                id="two_worktrees",
            ),
            pytest.param(
                {"worktrees": []},
                "git_worktree | ✓ | list · 0 worktrees",
                id="empty",
            ),
            pytest.param(
                {
                    "worktrees": [
                        {"path": "/bare", "bare": "true"},
                        {
                            "path": "/det",
                            "HEAD": "0123456789abcdef",
                            "detached": "true",
                        },
                    ]
                },
                (
                    "git_worktree | ✓ | list · 2 worktrees\n"
                    "/bare (bare)\n"
                    "/det 0123456 (detached)"
                ),
                id="detached_and_bare_flags",
            ),
        ],
    )
    def test_render_list_text(self, data: dict[str, Any], expected: str) -> None:
        assert render_list_text(data) == expected


class TestRenderAddText:
    """render_add_text: add sub-mode."""

    def test_add(self) -> None:
        data: dict[str, Any] = {
            "path": "/repo-feat",
            "branch": "feat/x",
            "base": "main",
        }
        assert render_add_text(data) == (
            "git_worktree | ✓ | add · feat/x @ main\n/repo-feat"
        )


class TestRenderRemoveText:
    """render_remove_text: remove sub-mode."""

    def test_remove(self) -> None:
        assert render_remove_text({"removed": "/repo-feat"}) == (
            "git_worktree | ✓ | remove\n/repo-feat"
        )


class TestRenderFailureText:
    """render_failure_text: failure branches."""

    def test_invalid_action(self) -> None:
        out = render_failure_text(error="Invalid action 'foo'.", data=None)
        assert out == "git_worktree | ✗ | Invalid action 'foo'."

    def test_suggestions_hint(self) -> None:
        data: dict[str, Any] = {"suggestions": ["sub1"]}
        out = render_failure_text(error="not a git repository", data=data)
        assert out == (
            "git_worktree | ✗ | not a git repository\nhint: pass one as path: sub1"
        )
