"""Tests for the verify MCP tool — TDD RED phase.

Tests that the verify tool orchestrates audit + init check + AST enrichment.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from axm.services.tools.base import ToolResult


class TestVerifyToolRegistered:
    """Verify tool must be discoverable on the MCP server."""

    def test_verify_function_importable(self) -> None:
        """verify_project should be importable from axm_mcp.verify."""
        from axm_mcp.verify import verify_project

        assert callable(verify_project)


class TestVerifyProject:
    """Tests for verify_project() orchestration logic."""

    @pytest.fixture()  # type: ignore[misc]
    def mock_tools(self) -> dict[str, MagicMock]:
        """Mock discovered tools dict."""
        audit_tool = MagicMock()
        audit_tool.execute.return_value = ToolResult(
            success=True,
            data={
                "score": 85,
                "grade": "B",
                "passed": ["QUALITY_LINT: ok"],
                "failed": [
                    {
                        "rule_id": "QUALITY_TYPE",
                        "message": "5 errors",
                        "details": {
                            "error_count": 5,
                            "errors": [
                                {
                                    "file": "src/foo.py",
                                    "line": 1,
                                    "message": "...",
                                    "code": "e",
                                },
                            ],
                        },
                        "fix_hint": "Add type hints",
                    }
                ],
            },
        )

        init_tool = MagicMock()
        init_tool.execute.return_value = ToolResult(
            success=True,
            data={
                "score": 90,
                "grade": "A",
                "passed": ["pyproject.exists: ok"],
                "failed": [],
            },
        )

        ast_tool = MagicMock()
        ast_tool.execute.return_value = ToolResult(
            success=True,
            data={"callers": ["cli.py:58"], "score": 0.7},
        )

        return {
            "audit": audit_tool,
            "init_check": init_tool,
            "ast_impact": ast_tool,
        }

    def test_returns_audit_and_governance(
        self, mock_tools: dict[str, MagicMock]
    ) -> None:
        """Verify returns both audit and governance sections."""
        from axm_mcp.verify import verify_project

        result = verify_project("/tmp/fake", mock_tools)
        assert "audit" in result
        assert "governance" in result

    def test_calls_both_tools(self, mock_tools: dict[str, MagicMock]) -> None:
        """Verify calls both audit and init_check tools."""
        from axm_mcp.verify import verify_project

        verify_project("/tmp/fake", mock_tools)
        mock_tools["audit"].execute.assert_called_once()
        mock_tools["init_check"].execute.assert_called_once()

    def test_graceful_without_init(self) -> None:
        """Verify works when axm-init is not installed."""
        from axm_mcp.verify import verify_project

        audit_tool = MagicMock()
        audit_tool.execute.return_value = ToolResult(
            success=True,
            data={"score": 85, "grade": "B", "passed": [], "failed": []},
        )
        tools = {"audit": audit_tool}  # No init_check

        result = verify_project("/tmp/fake", tools)
        assert "audit" in result
        assert result["governance"] is None

    def test_graceful_without_audit(self) -> None:
        """Verify works when axm-audit is not installed."""
        from axm_mcp.verify import verify_project

        tools: dict[str, Any] = {}  # Nothing installed

        result = verify_project("/tmp/fake", tools)
        assert result["audit"] is None
        assert result["governance"] is None

    @patch("axm_mcp.verify._enrich_failure")
    def test_enrichment_called_for_failures(
        self, mock_enrich: MagicMock, mock_tools: dict[str, MagicMock]
    ) -> None:
        """AST enrichment should be called when failures exist."""
        from axm_mcp.verify import verify_project

        mock_enrich.return_value = {"callers": [], "score": 0.5}

        verify_project("/tmp/fake", mock_tools)
        mock_enrich.assert_called()

    @patch("axm_mcp.verify._enrich_failure")
    def test_enrichment_skipped_no_failures(self, mock_enrich: MagicMock) -> None:
        """AST enrichment should NOT be called when no failures."""
        from axm_mcp.verify import verify_project

        audit_tool = MagicMock()
        audit_tool.execute.return_value = ToolResult(
            success=True,
            data={"score": 100, "grade": "A", "passed": ["ok"], "failed": []},
        )
        tools = {"audit": audit_tool}

        verify_project("/tmp/fake", tools)
        mock_enrich.assert_not_called()
