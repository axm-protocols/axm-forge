"""Tests for _resolve_working_dir helper."""

from __future__ import annotations

from pathlib import Path

from axm_git.hooks._resolve import _resolve_working_dir


class TestResolveWorkingDir:
    """Tests for _resolve_working_dir."""

    def test_resolve_working_dir_string(self) -> None:
        """String worktree_path returns Path directly."""
        context = {"worktree_path": "/tmp/wt"}
        result = _resolve_working_dir({}, context)
        assert result == Path("/tmp/wt")

    def test_resolve_working_dir_dict(self) -> None:
        """Dict worktree_path unwraps to the inner worktree_path value."""
        context = {
            "worktree_path": {"worktree_path": "/tmp/wt", "branch": "x"},
        }
        result = _resolve_working_dir({}, context)
        assert result == Path("/tmp/wt")

    def test_resolve_working_dir_params_override(self) -> None:
        """Params working_dir takes precedence over context."""
        params = {"working_dir": "/other"}
        context = {
            "worktree_path": {"worktree_path": "/tmp/wt", "branch": "x"},
        }
        result = _resolve_working_dir(params, context)
        assert result == Path("/other")

    def test_resolve_working_dir_fallback_working_dir(self) -> None:
        """Falls back to context working_dir when no worktree_path."""
        context = {"working_dir": "/fallback"}
        result = _resolve_working_dir({}, context)
        assert result == Path("/fallback")

    def test_resolve_working_dir_default(self) -> None:
        """Returns Path('.') when no params or context keys."""
        result = _resolve_working_dir({}, {})
        assert result == Path(".")

    def test_resolve_working_dir_custom_param_key(self) -> None:
        """Custom param_key reads from that key instead of working_dir."""
        params = {"path": "/custom"}
        result = _resolve_working_dir(params, {}, param_key="path")
        assert result == Path("/custom")
