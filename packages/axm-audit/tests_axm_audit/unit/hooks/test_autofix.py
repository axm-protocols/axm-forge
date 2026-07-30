from __future__ import annotations

import importlib.metadata


class TestAutofixHookRegistered:
    """Entry point 'audit:autofix' must be discoverable in axm.hooks."""

    def test_autofix_hook_registered(self) -> None:
        eps = importlib.metadata.entry_points(group="axm.hooks")
        names = [ep.name for ep in eps]
        assert "audit:autofix" in names


class TestExistingEntryPoints:
    """Existing entry points in axm.tools and axm.witnesses must still be present."""

    def test_existing_entry_points(self) -> None:
        tools_eps = importlib.metadata.entry_points(group="axm.tools")
        witnesses_eps = importlib.metadata.entry_points(group="axm.witnesses")

        # At least the known axm-audit entries must exist
        tool_names = [ep.name for ep in tools_eps]
        witness_names = [ep.name for ep in witnesses_eps]

        assert len(tool_names) > 0, "No axm.tools entry points found"
        assert len(witness_names) > 0, "No axm.witnesses entry points found"
