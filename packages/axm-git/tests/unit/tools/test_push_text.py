"""Unit tests for push_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.push_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_push_with_upstream_set(self) -> None:
        data: dict[str, Any] = {
            "branch": "feat/x",
            "remote": "origin",
            "pushed": True,
            "set_upstream": True,
        }
        assert render_text(data) == "git_push | ✓ | feat/x → origin · upstream set"

    def test_push_existing_upstream(self) -> None:
        data: dict[str, Any] = {
            "branch": "main",
            "remote": "origin",
            "pushed": True,
            "set_upstream": False,
        }
        assert render_text(data) == "git_push | ✓ | main → origin"


class TestRenderFailureText:
    """render_failure_text: failure branches."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="rejected: non-fast-forward", data=None)
        assert out == "git_push | ✗ | rejected: non-fast-forward"

    def test_dirty_tree(self) -> None:
        data: dict[str, Any] = {"dirty_files": ["a.py", "b.py"]}
        out = render_failure_text(
            error="Working tree is dirty. Commit or stash changes first.",
            data=data,
        )
        assert out == (
            "git_push | ✗ | Working tree is dirty. "
            "Commit or stash changes first.\n"
            "dirty: a.py, b.py"
        )

    def test_suggestions_hint(self) -> None:
        data: dict[str, Any] = {"suggestions": ["sub1"]}
        out = render_failure_text(error="not a git repository", data=data)
        assert out == (
            "git_push | ✗ | not a git repository\nhint: pass one as path: sub1"
        )
