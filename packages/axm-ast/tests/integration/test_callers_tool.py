"""Split from ``test_coverage_gaps.py``."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.callers import CallersTool
from tests.integration._helpers import _assert_tool_result


def _make_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "mypkg"
    for name, content in files.items():
        fp = pkg / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return pkg


class TestCallersToolWorkspace:
    """Cover tools/callers.py workspace branch (lines 61-65)."""

    def test_workspace_callers(self, tmp_path: Path, mocker: MagicMock) -> None:

        mock_caller = MagicMock()
        mock_caller.module = "mod_a"
        mock_caller.line = 10
        mock_caller.context = "func_a"
        mock_caller.call_expression = "greet()"

        mocker.patch(
            "axm_ast.core.workspace.detect_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value={"packages": []},
        )
        mocker.patch(
            "axm_ast.core.callers.find_callers_workspace",
            return_value=[mock_caller],
        )
        pkg = _make_pkg(tmp_path, {"__init__.py": ""})
        result = CallersTool().execute(path=str(pkg), symbol="greet")
        assert result.success is True
        assert result.data["count"] == 1


class TestCallersToolIntegration:
    """Tests for ast_callers tool."""

    def test_find_callers(self, sample_project: Path) -> None:

        tool = CallersTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"), symbol="greet")
        _assert_tool_result(result)
        assert result.success is True
        assert "callers" in result.data
        assert result.data["count"] >= 1

    def test_missing_symbol(self, sample_project: Path) -> None:

        tool = CallersTool()
        result = tool.execute(path=str(sample_project / "src" / "demo"))
        assert result.success is False
        assert result.error is not None


@pytest.fixture()
def callers_tool() -> CallersTool:
    return CallersTool()


class TestCallersIndirectResolution:
    """Callers with indirect=True on wrapped func → resolves through decorator."""

    def test_callers_indirect_resolution(
        self, callers_tool: CallersTool, simple_pkg: Path
    ) -> None:
        result = callers_tool.execute(path=str(simple_pkg), symbol="greet")
        assert result.success is True
        # greet is called by helper and wrapped — should find callers
        assert result.data["count"] >= 1
        caller_contexts = [c["module"] for c in result.data["callers"]]
        assert len(caller_contexts) >= 1


class TestCallersToolEdgeCasesIntegration:
    """CallersTool — exception."""

    def test_exception(
        self, callers_tool: CallersTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.callers.find_callers",
            side_effect=RuntimeError("callers boom"),
        )
        result = callers_tool.execute(path=str(simple_pkg), symbol="greet")
        assert result.success is False
        assert "callers boom" in (result.error or "")


@pytest.fixture()
def workspace_path(tmp_path: Path) -> Path:
    """Create a minimal directory that looks like a workspace."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'ws'\n")
    return tmp_path


@pytest.fixture()
def non_workspace_path(tmp_path: Path) -> Path:
    """A plain directory that is not a workspace."""
    return tmp_path


@pytest.fixture()
def fake_workspace() -> SimpleNamespace:
    return SimpleNamespace(packages=[], root=Path("/fake"))


@pytest.fixture()
def fake_caller() -> SimpleNamespace:
    return SimpleNamespace(
        module="mod.a",
        line=10,
        context="def foo(): call()",
        call_expression="call()",
    )


def test_callers_workspace_single_detection(
    workspace_path: Path,
    fake_workspace: SimpleNamespace,
    fake_caller: SimpleNamespace,
) -> None:
    """After fix, detect_workspace must NOT be called separately.

    analyze_workspace is tried directly; detect_workspace only runs
    internally inside analyze_workspace.
    """
    tool = CallersTool()

    with (
        patch(
            "axm_ast.core.workspace.detect_workspace",
            side_effect=AssertionError(
                "detect_workspace should not be called directly"
            ),
        ) as mock_detect,
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value=fake_workspace,
        ) as mock_analyze,
        patch(
            "axm_ast.core.callers.find_callers_workspace",
            return_value=[fake_caller],
        ),
    ):
        result = tool.execute(path=str(workspace_path), symbol="MyFunc")

    assert result.success is True
    mock_detect.assert_not_called()
    mock_analyze.assert_called_once()
    assert result.data["count"] == 1


def test_callers_nonworkspace_fallback(
    non_workspace_path: Path,
    fake_caller: SimpleNamespace,
) -> None:
    """When analyze_workspace raises ValueError the tool falls back to
    single-package analysis via get_package + find_callers.
    """
    tool = CallersTool()
    fake_pkg = SimpleNamespace(name="pkg")

    with (
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            side_effect=ValueError("not a workspace"),
        ),
        patch(
            "axm_ast.core.cache.get_package",
            return_value=fake_pkg,
        ) as mock_pkg,
        patch(
            "axm_ast.core.callers.find_callers",
            return_value=[fake_caller],
        ) as mock_find,
    ):
        result = tool.execute(path=str(non_workspace_path), symbol="MyFunc")

    assert result.success is True
    mock_pkg.assert_called_once()
    mock_find.assert_called_once()
    assert result.data["count"] == 1


def test_workspace_empty_packages(
    workspace_path: Path,
) -> None:
    """Workspace with zero packages — analyze_workspace succeeds but
    find_callers_workspace returns an empty list.
    """
    tool = CallersTool()
    empty_ws = SimpleNamespace(packages=[], root=workspace_path)

    with (
        patch(
            "axm_ast.core.workspace.analyze_workspace",
            return_value=empty_ws,
        ),
        patch(
            "axm_ast.core.callers.find_callers_workspace",
            return_value=[],
        ),
    ):
        result = tool.execute(path=str(workspace_path), symbol="Missing")

    assert result.success is True
    assert result.data["callers"] == []
    assert result.data["count"] == 0
