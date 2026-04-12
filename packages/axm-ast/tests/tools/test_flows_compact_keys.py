from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.tools.flows import FlowsTool


@pytest.fixture()
def _mock_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch core.cache and core.flows so FlowsTool.execute never hits disk."""
    pkg_mock = MagicMock()
    monkeypatch.setattr("axm_ast.core.cache.get_package", lambda _p: pkg_mock)
    monkeypatch.setattr(
        "axm_ast.core.flows.VALID_DETAILS", {"trace", "source", "compact"}
    )
    step = MagicMock(name="step", depth=1, chain=["a", "b"])
    step.name = "func"
    step.module = "mod"
    step.line = 10
    step.resolved_module = None
    step.source = None
    monkeypatch.setattr("axm_ast.core.flows.trace_flow", lambda *a, **kw: [step])
    monkeypatch.setattr(
        "axm_ast.core.flows.format_flow_compact", lambda steps: "main\n  └─ func"
    )


@pytest.fixture()
def tmp_pkg(tmp_path: object) -> object:
    """Create a minimal directory so is_dir() passes."""
    return tmp_path


# --- Unit tests ---


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_has_depth_key(tmp_pkg: object) -> None:
    tool = FlowsTool()
    result = tool.execute(
        path=str(tmp_pkg), entry="main", detail="compact", max_depth=3
    )
    assert result.success
    assert result.data["depth"] == 3


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_has_cross_module_key(tmp_pkg: object) -> None:
    tool = FlowsTool()
    result = tool.execute(
        path=str(tmp_pkg), entry="main", detail="compact", cross_module=True
    )
    assert result.success
    assert result.data["cross_module"] is True


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_keys_match_trace(tmp_pkg: object) -> None:
    """Compact data must contain exactly the expected key set."""
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="compact")
    assert result.success
    assert set(result.data.keys()) == {
        "entry",
        "compact",
        "depth",
        "cross_module",
        "count",
    }


# --- Edge case: default values ---


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_compact_default_values(tmp_pkg: object) -> None:
    """Without explicit max_depth/cross_module, defaults apply."""
    # defaults are depth=5, cross_module=False
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="compact")
    assert result.success
    assert result.data["depth"] == 5
    assert result.data["cross_module"] is False


# --- AC3: trace/source data dict remains unchanged ---


@pytest.mark.usefixtures("_mock_flows")
def test_flows_tool_trace_keys_unchanged(tmp_pkg: object) -> None:
    """Trace detail still returns steps-based keys, unaffected by compact fix."""
    tool = FlowsTool()
    result = tool.execute(path=str(tmp_pkg), entry="main", detail="trace")
    assert result.success
    assert set(result.data.keys()) == {
        "entry",
        "steps",
        "depth",
        "cross_module",
        "count",
    }
