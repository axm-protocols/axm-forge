"""Unit tests for pr_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.pr_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_pr_auto_merge(self) -> None:
        data: dict[str, Any] = {
            "pr_url": "https://github.com/acme/w/pull/42",
            "pr_number": "42",
            "auto_merge": True,
        }
        assert render_text(data) == (
            "git_pr | ✓ | #42 · auto-merge\nhttps://github.com/acme/w/pull/42"
        )

    def test_pr_no_auto_merge(self) -> None:
        data: dict[str, Any] = {
            "pr_url": "https://github.com/acme/w/pull/7",
            "pr_number": "7",
            "auto_merge": False,
        }
        assert render_text(data) == (
            "git_pr | ✓ | #7\nhttps://github.com/acme/w/pull/7"
        )


class TestRenderFailureText:
    """render_failure_text: failure branches."""

    def test_gh_unavailable(self) -> None:
        out = render_failure_text(error="gh CLI not available", data=None)
        assert out == "git_pr | ✗ | gh CLI not available"

    def test_suggestions_hint(self) -> None:
        data: dict[str, Any] = {"suggestions": ["sub1"]}
        out = render_failure_text(error="not a git repository", data=data)
        assert out == (
            "git_pr | ✗ | not a git repository\nhint: pass one as path: sub1"
        )
