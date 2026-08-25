"""Unit tests for await_merge_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.await_merge_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_merged_pr_summary(self) -> None:
        data: dict[str, Any] = {"pr_ref": "#42"}
        assert render_text(data) == "git_await_merge | ✓ | PR #42 merged"

    def test_missing_pr_ref_falls_back_to_empty(self) -> None:
        assert render_text({}) == "git_await_merge | ✓ | PR  merged"

    def test_non_str_pr_ref_coerced_to_empty(self) -> None:
        data: dict[str, Any] = {"pr_ref": 42}
        assert render_text(data) == "git_await_merge | ✓ | PR  merged"


class TestRenderFailureText:
    """render_failure_text: failure-path rendering."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="timed out waiting for merge")
        assert out == "git_await_merge | ✗ | timed out waiting for merge"
