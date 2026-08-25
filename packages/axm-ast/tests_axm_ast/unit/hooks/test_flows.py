"""Unit tests for axm_ast.hooks.flows."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

# ── build_trace_opts ──


class TestBuildTraceOpts:
    """build_trace_opts maps the 'detail' input to opts.detail / is_compact."""

    @pytest.mark.parametrize(
        ("detail", "expected_is_compact"),
        [
            pytest.param("compact", True, id="compact_passthrough"),
            pytest.param("trace", False, id="trace_unchanged"),
            pytest.param("source", False, id="source_detail"),
        ],
    )
    def test_detail_passthrough(self, detail: str, expected_is_compact: bool) -> None:
        from axm_ast.hooks.flows import build_trace_opts

        opts, is_compact = build_trace_opts({"detail": detail})
        assert opts.detail == detail
        assert is_compact is expected_is_compact


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
