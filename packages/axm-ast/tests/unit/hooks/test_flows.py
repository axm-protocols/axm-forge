"""Unit tests for axm_ast.hooks.flows."""

from __future__ import annotations

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
