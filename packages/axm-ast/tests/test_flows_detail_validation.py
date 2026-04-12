from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.core.flows import trace_flow
from axm_ast.hooks.flows import FlowsHook, _build_trace_opts
from axm_ast.tools.flows import FlowsTool

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestTraceFlowInvalidDetailRaises:
    """trace_flow() must reject detail values outside the valid set."""

    def test_trace_flow_invalid_detail_raises(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="full")


class TestTraceFlowValidDetailsAccepted:
    """trace_flow() accepts each of the three valid detail values."""

    @pytest.mark.parametrize("detail", ["trace", "source", "compact"])
    def test_trace_flow_valid_details_accepted(
        self, detail: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pkg = MagicMock()
        # Short-circuit BFS by making entry lookup return None
        monkeypatch.setattr(
            "axm_ast.core.flows._find_symbol_location",
            lambda *a, **kw: (None, None),
        )
        result = trace_flow(pkg, "main", detail=detail)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestFlowsToolInvalidDetail:
    """FlowsTool.execute() returns failure for invalid detail."""

    def test_flows_tool_invalid_detail(self, tmp_path: object) -> None:
        tool = FlowsTool()
        result = tool.execute(path=str(tmp_path), entry="main", detail="full")
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()


class TestFlowsToolValidDetails:
    """FlowsTool.execute() succeeds for each valid detail."""

    @pytest.mark.parametrize("detail", ["trace", "source", "compact"])
    def test_flows_tool_valid_details(
        self,
        detail: str,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_pkg = MagicMock()
        monkeypatch.setattr("axm_ast.core.cache.get_package", lambda *a, **kw: mock_pkg)
        monkeypatch.setattr("axm_ast.core.flows.trace_flow", lambda *a, **kw: [])
        monkeypatch.setattr(
            "axm_ast.core.flows.format_flow_compact", lambda *a, **kw: ""
        )
        tool = FlowsTool()
        result = tool.execute(path=str(tmp_path), entry="main", detail=detail)
        assert result.success is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDetailEdgeCases:
    """Boundary conditions for detail validation."""

    def test_empty_string_detail_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="")

    def test_case_sensitivity_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail="Trace")

    def test_none_detail_rejected(self) -> None:
        pkg = MagicMock()
        with pytest.raises(ValueError, match="detail"):
            trace_flow(pkg, "main", detail=None)  # type: ignore[arg-type]

    def test_build_trace_opts_invalid_detail(self) -> None:
        with pytest.raises(ValueError, match="detail"):
            _build_trace_opts({"detail": "full"})

    def test_flows_hook_invalid_detail(self, tmp_path: object) -> None:
        hook = FlowsHook()
        result = hook.execute(
            context={"working_dir": str(tmp_path)},
            entry="main",
            detail="full",
        )
        assert result.success is False
        assert result.error is not None
        assert "detail" in result.error.lower()
