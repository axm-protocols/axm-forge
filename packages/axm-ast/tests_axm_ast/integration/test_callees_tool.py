"""Split from ``test_callees.py``."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.callees import CalleesTool


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a temporary Python package from file name → content mapping."""
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestCalleesMCPToolIntegration:
    """CalleesTool MCP wrapper returns ToolResult."""

    def test_mcp_tool_success(self, tmp_path: Path) -> None:

        pkg_path = _make_pkg(
            tmp_path,
            {
                "__init__.py": "",
                "mod.py": ("def helper():\n    pass\n\ndef main():\n    helper()\n"),
            },
        )
        tool = CalleesTool()
        result = tool.execute(path=str(pkg_path), symbol="main")
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] >= 1
        callee = result.data["callees"][0]
        assert "call_expression" in callee
        assert "symbol" not in callee


class TestCalleesToolEdgeCasesIntegration:
    """CalleesTool — exception."""

    def test_exception(self, simple_pkg: Path, mocker: MagicMock) -> None:

        mocker.patch(
            "axm_ast.core.flows.find_callees",
            side_effect=RuntimeError("callees boom"),
        )
        result = CalleesTool().execute(path=str(simple_pkg), symbol="greet")
        assert result.success is False
        assert "callees boom" in (result.error or "")


@pytest.fixture()
def fake_callees():
    return [
        SimpleNamespace(
            module="pkg.mod",
            symbol="helper",
            line=10,
            call_expression="helper(x, y)",
        ),
        SimpleNamespace(
            module="pkg.util",
            symbol="run",
            line=25,
            call_expression="run()",
        ),
    ]


@pytest.fixture()
def tool():
    return CalleesTool()


def test_callees_output_no_symbol_key(
    tool: CalleesTool, fake_callees: list[SimpleNamespace], tmp_path: Path
) -> None:
    """callee_data dicts must NOT contain a 'symbol' key."""
    with (
        patch("axm_ast.core.flows.find_callees_workspace", return_value=fake_callees),
        patch("axm_ast.core.workspace.analyze_workspace"),
    ):
        result = tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success
    for callee in result.data["callees"]:
        assert "symbol" not in callee


def test_callees_has_call_expression(
    tool: CalleesTool, fake_callees: list[SimpleNamespace], tmp_path: Path
) -> None:
    """Each callee dict must contain a 'call_expression' key."""
    with (
        patch("axm_ast.core.flows.find_callees_workspace", return_value=fake_callees),
        patch("axm_ast.core.workspace.analyze_workspace"),
    ):
        result = tool.execute(path=str(tmp_path), symbol="Foo.bar")

    assert result.success
    for callee in result.data["callees"]:
        assert "call_expression" in callee
