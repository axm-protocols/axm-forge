"""Unit tests for pull_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.pull_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_remote_branch_summary(self) -> None:
        data: dict[str, Any] = {"remote": "origin", "branch": "main"}
        assert render_text(data) == "git_pull | ✓ | origin/main"

    def test_missing_keys_fall_back_to_empty(self) -> None:
        assert render_text({}) == "git_pull | ✓ | /"

    def test_non_str_values_coerced_to_empty(self) -> None:
        data: dict[str, Any] = {"remote": None, "branch": 0}
        assert render_text(data) == "git_pull | ✓ | /"


class TestRenderFailureText:
    """render_failure_text: failure-path rendering."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="could not pull: diverged")
        assert out == "git_pull | ✗ | could not pull: diverged"
