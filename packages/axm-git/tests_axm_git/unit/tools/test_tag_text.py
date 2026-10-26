"""Unit tests for tag_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

import pytest

from axm_git.tools.tag_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_full(self) -> None:
        data: dict[str, Any] = {
            "tag": "v0.4.0",
            "bump": "minor",
            "breaking": False,
            "resolved_version": "0.4.0",
            "pushed": True,
            "ci_check": "green",
            "commits_included": 7,
            "current_tag": "git/v0.3.1",
        }
        assert render_text(data) == (
            "git_tag | ✓ | v0.4.0 · minor · 7 commits · pushed\n"
            "resolved 0.4.0 · CI green · prev git/v0.3.1"
        )

    def test_text_shows_full_tag(self) -> None:
        """AC4: renderer surfaces the resolvable full_tag ref."""
        data: dict[str, Any] = {
            "tag": "v0.4.0",
            "full_tag": "git/v0.4.0",
            "bump": "minor",
            "breaking": False,
            "resolved_version": "0.4.0",
            "pushed": True,
            "ci_check": "green",
            "commits_included": 7,
            "current_tag": "git/v0.3.1",
        }
        assert "git/v0.4.0" in render_text(data)

    def test_git_evidence_and_remote_verification(self) -> None:
        data: dict[str, Any] = {
            "tag": "v0.4.0",
            "full_tag": "ast/v0.4.0",
            "bump": "minor",
            "breaking": False,
            "resolved_version": "0.4.0",
            "version_source": "git_tag",
            "tag_commit": "0123456789abcdef" * 2 + "01234567",
            "tag_object": "f" * 40,
            "pushed": True,
            "remote_verified": True,
            "ci_check": "green",
            "commits_included": 2,
            "current_tag": "ast/v0.3.0",
        }
        assert render_text(data) == (
            "git_tag | ✓ | ast/v0.4.0 · minor · 2 commits · pushed · remote verified\n"
            "resolved 0.4.0 from git tag · commit 0123456789ab · CI green"
            " · prev ast/v0.3.0"
        )

    def test_breaking_not_pushed_no_resolved(self) -> None:
        data: dict[str, Any] = {
            "tag": "v1.0.0",
            "bump": "major",
            "breaking": True,
            "resolved_version": None,
            "pushed": False,
            "ci_check": "skipped",
            "commits_included": 3,
            "current_tag": "none",
        }
        assert render_text(data) == (
            "git_tag | ✓ | v1.0.0 · major · breaking · 3 commits · not pushed\n"
            "CI skipped · prev none"
        )


class TestRenderFailureText:
    """render_failure_text: failure branches."""

    def test_plain_error(self) -> None:
        out = render_failure_text(error="Failed to create tag: boom", data=None)
        assert out == "git_tag | ✗ | Failed to create tag: boom"

    def test_dirty(self) -> None:
        data: dict[str, Any] = {"dirty_files": [" M a.py", "?? b.py"]}
        out = render_failure_text(error="Uncommitted changes — commit first", data=data)
        assert out == (
            "git_tag | ✗ | Uncommitted changes — commit first\ndirty:  M a.py, ?? b.py"
        )

    @pytest.mark.parametrize(
        ("error", "data", "expected"),
        [
            pytest.param(
                "No commits since last tag",
                {"current_tag": "git/v0.3.1"},
                "git_tag | ✗ | No commits since last tag\nprev git/v0.3.1",
                id="no_commits_shows_prev_tag",
            ),
            pytest.param(
                "CI is red — fix before tagging",
                {"ci_check": "red"},
                "git_tag | ✗ | CI is red — fix before tagging\nCI red",
                id="ci_red_shows_ci_state",
            ),
        ],
    )
    def test_failure_detail_line(
        self, error: str, data: dict[str, Any], expected: str
    ) -> None:
        assert render_failure_text(error=error, data=data) == expected

    @pytest.mark.parametrize(
        ("extra", "expected"),
        [
            pytest.param(
                {"tag_commit": None, "pushed": False},
                "ast/v0.4.0 kept locally · not pushed · remote unverified",
                id="unverified_local_tag",
            ),
            pytest.param(
                {"tag_commit": "a" * 40, "pushed": True},
                f"ast/v0.4.0 @ {'a' * 12} kept locally · pushed · remote unverified",
                id="pushed_remote_unverified",
            ),
        ],
    )
    def test_post_creation_failure_shows_tag_state(
        self, extra: dict[str, Any], expected: str
    ) -> None:
        """The tag left behind wins over the previous-tag detail line."""
        data: dict[str, Any] = {
            "full_tag": "ast/v0.4.0",
            "remote_verified": False,
            "current_tag": "ast/v0.3.0",
            "ci_check": "green",
            **extra,
        }
        out = render_failure_text(error="boom", data=data)
        assert out == f"git_tag | ✗ | boom\n{expected}"

    def test_suggestions_hint(self) -> None:
        data: dict[str, Any] = {"suggestions": ["sub1"]}
        out = render_failure_text(error="not a git repository", data=data)
        assert out == (
            "git_tag | ✗ | not a git repository\nhint: pass one as path: sub1"
        )
