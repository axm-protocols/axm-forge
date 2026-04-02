from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from axm_engine.services.tracing.models import hash_content


@pytest.fixture()
def mock_orchestrator() -> MagicMock:
    orch = MagicMock()
    return orch


def _call_log_external_step(
    mock_orch: MagicMock,
    result_str: str,
    tool_name: str = "test_tool",
) -> dict:
    """Call _log_external_step and return the kwargs passed to log_external_step."""
    with patch(
        "axm_engine.runtime.orchestrator.get_orchestrator",
        return_value=mock_orch,
    ):
        from axm_mcp.discovery import _log_external_step

        _log_external_step(
            tool_name=tool_name,
            tool_args={},
            success=True,
            result_str=result_str,
            duration_ms=10,
        )
    return mock_orch.log_external_step.call_args.kwargs


def test_hash_from_content_not_length(mock_orchestrator: MagicMock) -> None:
    """result_hash must be computed from actual content, not from len() string."""
    content = "hello world"
    kwargs = _call_log_external_step(mock_orchestrator, result_str=content)

    expected_hash = hash_content(content)
    assert kwargs["result_hash"] == expected_hash
    # Must NOT be the hash of the length string
    assert kwargs["result_hash"] != hash_content(str(len(content)))


def test_different_content_same_length(mock_orchestrator: MagicMock) -> None:
    """Two results with same length but different content must differ."""
    kwargs_abc = _call_log_external_step(mock_orchestrator, result_str="abc")
    kwargs_xyz = _call_log_external_step(mock_orchestrator, result_str="xyz")

    assert kwargs_abc["result_hash"] != kwargs_xyz["result_hash"]


def test_empty_result_hash(mock_orchestrator: MagicMock) -> None:
    """Empty result_str should produce hash_content('') — a consistent hash."""
    kwargs = _call_log_external_step(mock_orchestrator, result_str="")

    assert kwargs["result_hash"] == hash_content("")


def test_manager_uses_provided_hash_without_recompute() -> None:
    """When caller passes non-empty result_hash, manager must use it as-is."""
    from axm_engine.services.tracing.manager import TracingManager

    manager = TracingManager(store=MagicMock())
    tracer = MagicMock()
    manager._active_session_id = "sess-1"
    manager._tracers = {"sess-1": tracer}

    provided_hash = "custom_hash_42"
    manager.log_external_step(
        tool_name="t",
        result_hash=provided_hash,
        result_output="some content",
    )

    call_kwargs = tracer.log_step.call_args.kwargs
    assert call_kwargs["result_hash"] == provided_hash
