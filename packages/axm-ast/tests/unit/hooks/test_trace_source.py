"""Unit tests for axm_ast.hooks.trace_source — input validation only (no I/O)."""

from __future__ import annotations

import pytest

from axm_ast.hooks.trace_source import TraceSourceHook


class TestTraceSourceHookValidation:
    """Input validation tests for TraceSourceHook.execute (no I/O)."""

    @pytest.fixture()
    def hook(self) -> TraceSourceHook:
        return TraceSourceHook()

    def test_missing_entry_param(self, hook: TraceSourceHook) -> None:
        result = hook.execute(context={"working_dir": "."})
        assert not result.success
        assert "entry" in (result.error or "")

    def test_bad_working_dir(self, hook: TraceSourceHook) -> None:
        result = hook.execute(
            context={"working_dir": "/nonexistent/path"},
            entry="foo",
        )
        assert not result.success
