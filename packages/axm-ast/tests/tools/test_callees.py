from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_ast.tools.callees import CalleesTool


def test_callees_tool_workspace_path(tmp_path: Path) -> None:
    """CalleesTool at workspace root returns callees with :: prefixed modules."""
    call_site = MagicMock(
        module="pkg_a::utils",
        symbol="helper",
        line=42,
        context="helper(x)",
        call_expression="helper(x)",
    )

    ws = MagicMock()

    with (
        patch("axm_ast.core.workspace.analyze_workspace", return_value=ws),
        patch(
            "axm_ast.core.flows.find_callees_workspace",
            return_value=[call_site],
        ),
    ):
        tool = CalleesTool()
        result = tool.execute(path=str(tmp_path), symbol="my_func")

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["callees"][0]["module"] == "pkg_a::utils"


def test_callees_tool_single_package_fallback(tmp_path: Path) -> None:
    """CalleesTool at single package path falls back — no :: prefix."""
    call_site = MagicMock(
        module="core.utils",
        symbol="helper",
        line=10,
        context="helper()",
        call_expression="helper()",
    )

    pkg = MagicMock()

    with (
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            side_effect=ValueError("not a workspace"),
        ),
        patch("axm_ast.core.cache.get_package", return_value=pkg),
        patch("axm_ast.core.flows.find_callees", return_value=[call_site]),
    ):
        tool = CalleesTool()
        result = tool.execute(path=str(tmp_path), symbol="my_func")

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["callees"][0]["module"] == "core.utils"
    assert "::" not in result.data["callees"][0]["module"]
