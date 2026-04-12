from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.callees import CalleesTool


@pytest.fixture()
def tool() -> CalleesTool:
    return CalleesTool()


def _make_callsite(**overrides: object) -> SimpleNamespace:
    defaults = {
        "module": "pkg.mod",
        "symbol": "helper",
        "line": 10,
        "context": "some_caller",
        "call_expression": "helper()",
    }
    return SimpleNamespace(**(defaults | overrides))


def test_callees_output_no_context_key(tool: CalleesTool, tmp_path: str) -> None:
    """AC1: callee dicts must NOT contain 'context' key."""
    fake_callees = [_make_callsite(), _make_callsite(symbol="other", line=20)]

    with (
        patch(
            "axm_ast.core.cache.get_package",
            return_value=SimpleNamespace(),
        ),
        patch(
            "axm_ast.core.flows.find_callees",
            return_value=fake_callees,
        ),
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            side_effect=ValueError,
        ),
    ):
        result = tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success is True
    for callee in result.data["callees"]:
        assert "context" not in callee, (
            f"callee dict should not have 'context': {callee}"
        )
        # Ensure other expected keys are present
        assert "module" in callee
        assert "symbol" in callee
        assert "line" in callee
        assert "call_expression" in callee


def test_callers_still_has_context(tmp_path: str) -> None:
    """AC2: CallersTool output must still include 'context'."""
    from axm_ast.tools.callers import CallersTool

    caller_tool = CallersTool()
    fake_callers = [_make_callsite(symbol="caller_fn", line=5)]

    with (
        patch(
            "axm_ast.core.cache.get_package",
            return_value=SimpleNamespace(),
        ),
        patch(
            "axm_ast.core.callers.find_callers",
            return_value=fake_callers,
        ),
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            side_effect=ValueError,
        ),
    ):
        result = caller_tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success is True
    for caller in result.data["callers"]:
        assert "context" in caller, f"caller dict must have 'context': {caller}"
