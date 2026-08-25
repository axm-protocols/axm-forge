"""Unit tests for merge_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.merge_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_squash_merge_summary(self) -> None:
        data: dict[str, Any] = {"merged": "feat/x", "into": "main"}
        assert render_text(data) == "git_merge | ✓ | feat/x → main (squash)"

    def test_missing_keys_fall_back_to_empty(self) -> None:
        assert render_text({}) == "git_merge | ✓ |  →  (squash)"

    def test_non_str_values_coerced_to_empty(self) -> None:
        data: dict[str, Any] = {"merged": 1, "into": None}
        assert render_text(data) == "git_merge | ✓ |  →  (squash)"


class TestRenderFailureText:
    """render_failure_text: failure-path rendering."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="merge --squash failed: conflict")
        assert out == "git_merge | ✗ | merge --squash failed: conflict"
