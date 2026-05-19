"""Integration tests for AST Hooks discovery via entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

pytestmark = pytest.mark.integration


def test_hook_discovery_via_entry_points() -> None:
    """AC6: ast:context and ast:flows are discoverable via entry points.

    Tests discovery using importlib.metadata, which simulates HookRegistry
    without adding a dependency on axm-engine.
    """
    eps = entry_points(group="axm.hooks")
    registered_names = [ep.name for ep in eps]

    assert "ast:context" in registered_names
    assert "ast:flows" in registered_names
