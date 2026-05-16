"""Unit tests for axm_git.hooks.pull (no real I/O)."""

from __future__ import annotations

from axm_git.hooks.pull import PullHook


class TestPullHookUnit:
    """Unit-scope helpers for PullHook (no real I/O)."""

    def test_pull_hook_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = PullHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"


class TestPullHookDiscoverable:
    """Functional test for entry point discovery."""

    def test_pull_hook_discoverable(self) -> None:
        """git:pull-main entry point resolves to PullHook."""
        from importlib.metadata import entry_points

        eps = entry_points(group="axm.hooks", name="git:pull-main")
        assert len(list(eps)) == 1
        hook_cls = next(iter(eps)).load()
        assert hook_cls is PullHook
