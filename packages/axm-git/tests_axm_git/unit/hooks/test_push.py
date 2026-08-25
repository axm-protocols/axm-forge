"""Unit tests for axm_git.hooks.push (no real I/O)."""

from __future__ import annotations

from axm_git.hooks.push import PushHook


class TestPushHookUnit:
    """Unit-scope helpers for PushHook (no real I/O)."""

    def test_push_hook_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = PushHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"
