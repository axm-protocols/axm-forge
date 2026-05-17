"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path
from unittest.mock import MagicMock

from axm_ast.tools.context import ContextTool
from tests.integration._helpers import _assert_tool_result


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestContextToolWorkspace:
    """Cover tools/context.py workspace branch (lines 56, 58-59)."""

    def test_workspace_context(self, tmp_path: Path, mocker: MagicMock) -> None:

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.build_workspace_context",
            return_value={"workspace": True, "packages": []},
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = ContextTool().execute(path=str(pkg))
        assert result.success is True
        assert result.data["workspace"] is True


class TestContextToolIntegration:
    """Tests for ast_context tool."""

    def test_execute_returns_tool_result(self, sample_project: Path) -> None:

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        _assert_tool_result(result)
        assert result.success is True

    def test_execute_has_name_key(self, sample_project: Path) -> None:

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert "name" in result.data

    # --- Depth 0 compact output ---

    def test_context_tool_depth0(self, sample_project: Path) -> None:
        """depth=0 returns compact data with top_modules."""

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), depth=0)
        assert result.success is True
        assert "top_modules" in result.data
        assert "modules" not in result.data

    def test_context_tool_default_unchanged(self, sample_project: Path) -> None:
        """AC4: default behavior unchanged (regression)."""

        tool = ContextTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is True
        # depth=1 (default) returns 'packages' grouping, not raw 'modules'
        assert "packages" in result.data
        assert "patterns" in result.data


class TestContextToolException:
    """ContextTool — exception handling."""

    def test_exception(self, simple_pkg: Path, mocker: MagicMock) -> None:
        from axm_ast.tools.context import ContextTool

        mocker.patch(
            "axm_ast.core.context.build_context",
            side_effect=RuntimeError("ctx boom"),
        )
        result = ContextTool().execute(path=str(simple_pkg))
        assert result.success is False
        assert "ctx boom" in (result.error or "")
