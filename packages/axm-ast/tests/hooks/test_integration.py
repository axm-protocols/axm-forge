"""Integration tests for AST Hooks."""

from importlib.metadata import entry_points


def test_hook_discovery_via_entry_points() -> None:
    """AC6: ast:context and ast:flows are discoverable via entry points.

    Tests discovery using importlib.metadata, which simulates HookRegistry
    without adding a dependency on axm-engine.
    """
    eps = entry_points(group="axm.hooks")
    registered_names = [ep.name for ep in eps]

    assert "ast:context" in registered_names
    assert "ast:flows" in registered_names
