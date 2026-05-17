"""Unit tests for commit_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

import pytest

from axm_git.tools.commit_text import (
    format_commit_line,
    format_text_header,
    render_failure_text,
    render_text,
)


class TestFormatTextHeader:
    """format_text_header: header line variants."""

    def test_basic_header(self) -> None:
        assert (
            format_text_header(status="ok", succeeded=2, total=2)
            == "git_commit | ok | 2/2 commits"
        )

    def test_header_with_retried(self) -> None:
        assert (
            format_text_header(status="ok", succeeded=6, total=6, retried_count=1)
            == "git_commit | ok | 6/6 commits · 1 retried"
        )

    def test_header_with_extra(self) -> None:
        line = format_text_header(
            status="error", succeeded=0, total=1, extra="pre-commit failed at #1"
        )
        assert line == "git_commit | error | 0/1 commits · pre-commit failed at #1"

    def test_header_with_retried_and_extra(self) -> None:
        line = format_text_header(
            status="error",
            succeeded=1,
            total=2,
            retried_count=1,
            extra="pre-commit failed at #2 (retried)",
        )
        assert line == (
            "git_commit | error | 1/2 commits · 1 retried "
            "· pre-commit failed at #2 (retried)"
        )

    def test_pure_error_shape_when_total_zero(self) -> None:
        assert (
            format_text_header(
                status="error", succeeded=0, total=0, extra="no commits provided"
            )
            == "git_commit | error: no commits provided"
        )


class TestFormatCommitLine:
    """format_commit_line: per-commit line."""

    @pytest.mark.parametrize(
        ("sha", "message", "retried", "expected"),
        [
            pytest.param(
                "aa83f25", "feat: add a", False, "aa83f25 feat: add a", id="plain"
            ),
            pytest.param("1b60588", "feat: a", True, "1b60588 ↻ feat: a", id="retried"),
        ],
    )
    def test_commit_line(
        self, sha: str, message: str, retried: bool, expected: str
    ) -> None:
        result: dict[str, Any] = {"sha": sha, "message": message, "retried": retried}
        assert format_commit_line(result) == expected


class TestRenderText:
    """render_text: success-path rendering."""

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            pytest.param(
                {
                    "results": [
                        {
                            "sha": "87841bb",
                            "message": "feat: add b",
                            "precommit_passed": True,
                            "retried": False,
                        },
                        {
                            "sha": "0d2d6e0",
                            "message": "feat: add c",
                            "precommit_passed": True,
                            "retried": False,
                        },
                    ],
                    "total": 2,
                    "succeeded": 2,
                },
                (
                    "git_commit | ok | 2/2 commits\n"
                    "87841bb feat: add b\n0d2d6e0 feat: add c"
                ),
                id="two_commits",
            ),
            pytest.param(
                {
                    "results": [
                        {
                            "sha": "1b60588",
                            "message": "feat: a",
                            "precommit_passed": True,
                            "retried": True,
                        }
                    ],
                    "total": 1,
                    "succeeded": 1,
                },
                "git_commit | ok | 1/1 commits · 1 retried\n1b60588 ↻ feat: a",
                id="retried",
            ),
        ],
    )
    def test_render(self, data: dict[str, Any], expected: str) -> None:
        assert render_text(data) == expected


class TestRenderFailureText:
    """render_failure_text: every failure branch."""

    def test_plain_error_no_data(self) -> None:
        out = render_failure_text(error="No commits provided", data=None)
        assert out == "git_commit | error: no commits provided"

    def test_suggestions_branch(self) -> None:
        data = {
            "suggestions": ["sub1", "sub2"],
        }
        out = render_failure_text(error="fatal: not a git repository (...)", data=data)
        assert out == (
            "git_commit | error: not a git repository\n"
            "hint: child repos found — pass one as path: sub1, sub2"
        )

    def test_validation_branch_empty_files(self) -> None:
        data = {"results": [], "total": 1, "succeeded": 0}
        out = render_failure_text(error="Commit 1: empty files list", data=data)
        assert out == ("git_commit | error | 0/1 commits\ncommit 1: empty files list")

    def test_validation_branch_git_add_failed(self) -> None:
        data = {"results": [], "total": 1, "succeeded": 0}
        error = (
            "Commit 1: git add failed: "
            "fatal: pathspec 'nope.txt' did not match any files"
        )
        out = render_failure_text(error=error, data=data)
        assert out == (
            "git_commit | error | 0/1 commits\n"
            "commit 1: git add failed — fatal: pathspec 'nope.txt' "
            "did not match any files"
        )

    def test_failed_commit_with_auto_fixed_files(self) -> None:
        data = {
            "results": [
                {
                    "sha": "aa83f25",
                    "message": "feat: add a",
                    "precommit_passed": True,
                    "retried": False,
                }
            ],
            "total": 2,
            "succeeded": 1,
            "failed_commit": {
                "index": 2,
                "message": "feat: add b",
                "precommit_output": "ruff: line too long\nFound 1 errors.",
                "auto_fixed_files": ["src/foo.py", "src/bar.py"],
                "retried": True,
            },
        }
        out = render_failure_text(error="Commit 2: pre-commit failed", data=data)
        assert out == (
            "git_commit | error | 1/2 commits · "
            "pre-commit failed at #2 (retried)\n"
            "ok: aa83f25 feat: add a\n"
            "fail: feat: add b\n"
            "auto-fixed: src/foo.py, src/bar.py\n"
            "hook output:\n"
            "  ruff: line too long\n"
            "  Found 1 errors."
        )

    def test_failed_commit_without_auto_fixed_files(self) -> None:
        data = {
            "results": [],
            "total": 1,
            "succeeded": 0,
            "failed_commit": {
                "index": 1,
                "message": "feat: a",
                "precommit_output": "Linter rejected: trailing whitespace",
                "auto_fixed_files": [],
                "retried": False,
            },
        }
        out = render_failure_text(error="Commit 1: pre-commit failed", data=data)
        assert out == (
            "git_commit | error | 0/1 commits · pre-commit failed at #1\n"
            "fail: feat: a\n"
            "hook output:\n"
            "  Linter rejected: trailing whitespace"
        )
