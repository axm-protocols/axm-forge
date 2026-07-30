"""Unit tests for clone_text rendering helpers (pure functions, no I/O)."""

from __future__ import annotations

from typing import Any

from axm_git.tools.clone_text import render_failure_text, render_text


class TestRenderText:
    """render_text: success-path rendering."""

    def test_clone(self) -> None:
        data: dict[str, Any] = {
            "url": "https://github.com/acme/widgets.git",
            "dest": "widgets",
            "path": "/work/widgets",
            "cloned": True,
        }
        assert render_text(data) == (
            "git_clone | ✓ | https://github.com/acme/widgets.git → widgets\n"
            "/work/widgets"
        )

    def test_clone_without_path(self) -> None:
        data: dict[str, Any] = {"url": "u", "dest": "d", "cloned": True}
        assert render_text(data) == "git_clone | ✓ | u → d"


class TestRenderFailureText:
    """render_failure_text: failure rendering."""

    def test_error(self) -> None:
        out = render_failure_text(error="fatal: repository not found")
        assert out == "git_clone | ✗ | fatal: repository not found"
