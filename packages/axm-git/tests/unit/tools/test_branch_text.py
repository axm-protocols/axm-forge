"""Unit tests for branch_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.branch_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_branch(self) -> None:
        data: dict[str, Any] = {"branch": "feat/x"}
        assert render_text(data) == "git_branch | ✓ | feat/x"


class TestRenderFailureText:
    """render_failure_text: failure branches."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="fatal: branch exists", data=None)
        assert out == "git_branch | ✗ | fatal: branch exists"

    def test_suggestions_hint(self) -> None:
        data: dict[str, Any] = {"suggestions": ["sub1", "sub2"]}
        out = render_failure_text(error="not a git repository", data=data)
        assert out == (
            "git_branch | ✗ | not a git repository\nhint: pass one as path: sub1, sub2"
        )

    def test_data_without_suggestions(self) -> None:
        out = render_failure_text(error="boom", data={"other": "x"})
        assert out == "git_branch | ✗ | boom"
