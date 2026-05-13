from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_ast.tools.impact import ImpactTool


@pytest.fixture
def tool() -> ImpactTool:
    return ImpactTool()


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


class TestCompactSingleReturnsText:
    """AC1: _execute_single compact returns text, not data."""

    def test_compact_single_returns_text(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_analysis = {"symbol": "foo", "dependents": []}
        compact_md = "# Impact: foo\nNo dependents."

        with (
            patch.object(tool, "_analyze_single", return_value=fake_analysis),
            patch(
                "axm_ast.tools.impact.format_impact_compact",
                return_value=compact_md,
            ),
        ):
            result = tool._execute_single(
                project_path, symbol="foo", exclude_tests=False, detail="compact"
            )

        assert result.success is True
        assert result.text is not None
        assert result.text == compact_md
        assert result.data == {}


class TestCompactBatchReturnsText:
    """AC2: _execute_batch compact returns text, not data."""

    def test_compact_batch_returns_text(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_a = {"symbol": "a", "dependents": []}
        fake_b = {"symbol": "b", "dependents": []}
        compact_md = "# Impact: a, b\nNo dependents."

        with (
            patch.object(tool, "_analyze_single", side_effect=[fake_a, fake_b]),
            patch(
                "axm_ast.tools.impact.format_impact_compact",
                return_value=compact_md,
            ),
        ):
            result = tool._execute_batch(
                project_path,
                symbols=["a", "b"],
                exclude_tests=False,
                detail="compact",
            )

        assert result.success is True
        assert result.text is not None
        assert result.text == compact_md
        assert result.data == {}


class TestNonCompactReturnsData:
    """AC3: Non-compact mode returns structured data, text is None."""

    def test_non_compact_single_returns_data(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        from axm.tools.base import ToolResult

        fake_result = ToolResult(
            success=True, data={"symbol": "foo", "dependents": ["bar"]}
        )

        with patch.object(tool, "_analyze_single_result", return_value=fake_result):
            result = tool._execute_single(
                project_path, symbol="foo", exclude_tests=False, detail=None
            )

        assert result.data != {}
        assert result.data == {"symbol": "foo", "dependents": ["bar"]}
        assert result.text is None

    def test_non_compact_batch_returns_data(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        fake_a = {"symbol": "a", "dependents": []}
        fake_b = {"symbol": "b", "dependents": ["c"]}

        with patch.object(tool, "_analyze_single", side_effect=[fake_a, fake_b]):
            result = tool._execute_batch(
                project_path,
                symbols=["a", "b"],
                exclude_tests=False,
                detail=None,
            )

        assert result.success is True
        assert result.data == {"symbols": [fake_a, fake_b]}
        assert result.text is None


class TestEdgeCases:
    """Edge cases for compact output."""

    def test_empty_symbol_list_compact(
        self, tool: ImpactTool, project_path: Path
    ) -> None:
        result = tool._execute_batch(
            project_path,
            symbols=[],
            exclude_tests=False,
            detail="compact",
        )

        assert result.success is False
        assert result.error is not None
