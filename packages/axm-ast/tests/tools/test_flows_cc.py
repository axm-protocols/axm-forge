from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.flows import FlowsTool


@pytest.fixture()
def tool() -> FlowsTool:
    return FlowsTool()


@pytest.fixture()
def mock_pkg():
    return SimpleNamespace(name="fakepkg")


@pytest.fixture()
def _patch_dir(tmp_path):
    """Ensure the path passed to execute is a real directory."""
    return str(tmp_path)


def _make_entry(
    name: str, module: str, kind: str, line: int, framework: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name, module=module, kind=kind, line=line, framework=framework
    )


def _make_flow_step(
    name: str,
    module: str,
    line: int,
    depth: int,
    chain: list[str],
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        module=module,
        line=line,
        depth=depth,
        chain=chain,
        resolved_module=None,
        source=None,
    )


# ---------- Unit tests ----------


def test_flows_execute_entry_points(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute without entry param returns entry_points data."""
    entries = [
        _make_entry("main", "cli", "function", 10, "click"),
        _make_entry("app", "web", "function", 20, "fastapi"),
    ]
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.find_entry_points", return_value=entries),
    ):
        result = tool.execute(path=str(tmp_path))

    assert result.success is True
    assert result.data["count"] == 2
    assert len(result.data["entry_points"]) == 2
    assert result.data["entry_points"][0]["name"] == "main"
    assert result.data["entry_points"][1]["name"] == "app"


def test_flows_execute_trace(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute with entry='main' returns steps data with depth/count."""
    steps = [
        _make_flow_step("main", "cli", 10, 0, ["main"]),
        _make_flow_step("run", "cli", 30, 1, ["main", "run"]),
    ]
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.trace_flow", return_value=(steps, False)),
    ):
        result = tool.execute(path=str(tmp_path), entry="main")

    assert result.success is True
    assert result.data["entry"] == "main"
    assert result.data["count"] == 2
    assert result.data["depth"] == 1
    assert result.data["truncated"] is False
    assert len(result.data["steps"]) == 2
    assert result.data["steps"][0]["name"] == "main"
    assert result.data["steps"][1]["name"] == "run"


def test_flows_execute_compact(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """Call execute with detail='compact' returns compact tree string."""
    steps = [
        _make_flow_step("main", "cli", 10, 0, ["main"]),
    ]
    compact_tree = "main\n└── run"
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch("axm_ast.core.flows.trace_flow", return_value=(steps, False)),
        patch("axm_ast.core.flows.format_flow_compact", return_value=compact_tree),
    ):
        result = tool.execute(path=str(tmp_path), entry="main", detail="compact")

    assert result.success is True
    assert result.data["compact"] == compact_tree
    assert result.data["traces"] == compact_tree
    assert result.data["entry"] == "main"
    assert result.data["depth"] == 0
    assert result.data["count"] == 1


# ---------- Edge cases ----------


def test_flows_execute_invalid_detail(tool: FlowsTool, tmp_path: Path) -> None:
    """Invalid detail mode returns success=False with error."""
    with patch("axm_ast.core.cache.get_package", return_value=SimpleNamespace()):
        result = tool.execute(path=str(tmp_path), detail="invalid")

    assert result.success is False
    assert result.error is not None
    assert "invalid" in result.error.lower() or "Invalid" in result.error


def test_flows_execute_symbol_not_found(
    tool: FlowsTool, mock_pkg: SimpleNamespace, tmp_path: Path
) -> None:
    """entry='nonexistent' returns success=False."""
    with (
        patch("axm_ast.core.cache.get_package", return_value=mock_pkg),
        patch(
            "axm_ast.core.flows.trace_flow",
            side_effect=ValueError("Symbol 'nonexistent' not found in package"),
        ),
    ):
        result = tool.execute(path=str(tmp_path), entry="nonexistent")

    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()
