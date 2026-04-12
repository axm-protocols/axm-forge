from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_ast.tools.callers import CallersTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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


def test_invalid_path_returns_error() -> None:
    """Path that does not exist returns ToolResult(success=False)."""
    tool = CallersTool()
    result = tool.execute(path="/nonexistent/path/xyz", symbol="Foo")

    assert result.success is False
    assert "Not a directory" in (result.error or "")
