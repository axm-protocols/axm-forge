"""Unit tests for axm_ast.hooks.flows."""

from __future__ import annotations

from importlib.metadata import entry_points

# ── build_trace_opts ──


class TestBuildTraceOptsCompactPassthrough:
    """build_trace_opts must pass 'compact' through to opts.detail."""

    def test_compact_passthrough(self) -> None:
        from axm_ast.hooks.flows import build_trace_opts

        opts, is_compact = build_trace_opts({"detail": "compact"})
        assert opts.detail == "compact"
        assert is_compact is True

    def test_trace_unchanged(self) -> None:
        from axm_ast.hooks.flows import build_trace_opts

        opts, is_compact = build_trace_opts({"detail": "trace"})
        assert opts.detail == "trace"
        assert is_compact is False


class TestBuildTraceOptsEdgeCases:
    """Non-compact details must pass through unchanged."""

    def test_source_detail(self) -> None:
        from axm_ast.hooks.flows import build_trace_opts

        opts, is_compact = build_trace_opts({"detail": "source"})
        assert opts.detail == "source"
        assert is_compact is False


class TestHookEntryPointsDeclared:
    """axm.hooks entry points are declared for ast:context and ast:flows."""

    def test_hook_discovery_via_entry_points(self) -> None:
        """AC6: ast:context and ast:flows are discoverable via entry points.

        Tests discovery using importlib.metadata, which simulates HookRegistry
        without adding a dependency on axm-engine.
        """
        eps = entry_points(group="axm.hooks")
        registered_names = [ep.name for ep in eps]

        assert "ast:context" in registered_names
        assert "ast:flows" in registered_names
