"""Tests for hook entry point discoverability."""

from __future__ import annotations

from importlib.metadata import entry_points


class TestHookDiscovery:
    """Verify hooks are discoverable via entry points."""

    def test_preflight_hook_discoverable(self) -> None:
        eps = entry_points(group="axm.hooks")
        names = [ep.name for ep in eps]
        assert "git:preflight" in names

    def test_commit_phase_hook_discoverable(self) -> None:
        eps = entry_points(group="axm.hooks")
        names = [ep.name for ep in eps]
        assert "git:commit-phase" in names

    def test_preflight_hook_loads(self) -> None:
        eps = entry_points(group="axm.hooks")
        ep = next(ep for ep in eps if ep.name == "git:preflight")
        cls = ep.load()
        assert cls.__name__ == "PreflightHook"

    def test_commit_phase_hook_loads(self) -> None:
        eps = entry_points(group="axm.hooks")
        ep = next(ep for ep in eps if ep.name == "git:commit-phase")
        cls = ep.load()
        assert cls.__name__ == "CommitPhaseHook"
