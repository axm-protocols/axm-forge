"""Tests for tool edge cases — AXM-982 coverage gaps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.diff import DiffTool


@pytest.fixture()
def diff_tool() -> DiffTool:
    return DiffTool()


# ─── DiffTool ────────────────────────────────────────────────────────────────


class TestDiffNoChanges:
    """Call diff tool on identical trees → empty diff."""

    def test_diff_no_changes(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mock_diff = mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={"added": [], "removed": [], "modified": []},
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="main")
        assert result.success is True
        assert result.data["added"] == []
        assert result.data["removed"] == []
        assert result.data["modified"] == []
        mock_diff.assert_called_once()


class TestDiffDeletedSymbol:
    """Call diff on tree where symbol was removed → reports deletion."""

    def test_diff_deleted_symbol(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={
                "added": [],
                "removed": [{"symbol": "greet", "module": "core"}],
                "modified": [],
            },
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is True
        assert len(result.data["removed"]) == 1
        assert result.data["removed"][0]["symbol"] == "greet"


# ─── Additional edge-case coverage (AXM-982) ────────────────────────────────


class TestDiffErrorResult:
    """structural_diff returns dict with 'error' key → tool returns failure."""

    def test_diff_error_in_result(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            return_value={"error": "refs not found"},
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is False
        assert result.error == "refs not found"


class TestDiffException:
    """structural_diff raises → tool catches gracefully."""

    def test_diff_exception(
        self, diff_tool: DiffTool, simple_pkg: Path, mocker: MagicMock
    ) -> None:
        mocker.patch(
            "axm_ast.core.structural_diff.structural_diff",
            side_effect=RuntimeError("git failed"),
        )
        result = diff_tool.execute(path=str(simple_pkg), base="main", head="feature")
        assert result.success is False
        assert "git failed" in (result.error or "")
