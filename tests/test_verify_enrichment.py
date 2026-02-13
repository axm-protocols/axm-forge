"""TDD tests for AST enrichment: _extract_symbols and _enrich_failure.

RED phase — these test functions that don't exist yet.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from axm.tools.base import ToolResult

# ── _extract_symbols tests ───────────────────────────────────────────────────


class TestExtractSymbols:
    """Tests for _extract_symbols — multi-symbol extraction from failures."""

    def test_from_mypy_errors(self) -> None:
        """Extract unique module paths from mypy error entries."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {
                        "file": "src/foo/bar.py",
                        "line": 7,
                        "message": "...",
                        "code": "no-untyped-def",
                    },
                    {
                        "file": "src/foo/bar.py",
                        "line": 15,
                        "message": "...",
                        "code": "no-untyped-def",
                    },
                    {
                        "file": "src/baz/qux.py",
                        "line": 3,
                        "message": "...",
                        "code": "attr-defined",
                    },
                ]
            },
        }
        symbols = _extract_symbols(failure)
        assert set(symbols) == {"foo.bar", "baz.qux"}

    def test_from_complexity_functions(self) -> None:
        """Extract function names from complexity details."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "QUALITY_COMPLEXITY",
            "details": {
                "top_offenders": [
                    {"file": "auditor.py", "function": "audit_project", "cc": 15},
                ]
            },
        }
        symbols = _extract_symbols(failure)
        assert symbols == ["audit_project"]

    def test_fallback_message_parsing(self) -> None:
        """Fallback to 'Function X' pattern in message."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "SOME_OTHER_RULE",
            "message": "Function process_data has too many arguments",
            "details": None,
        }
        symbols = _extract_symbols(failure)
        assert symbols == ["process_data"]

    def test_none_details(self) -> None:
        """details=None → empty list."""
        from axm_mcp.verify import _extract_symbols

        failure = {"rule_id": "QUALITY_TYPE", "details": None}
        symbols = _extract_symbols(failure)
        assert symbols == []

    def test_deduplication(self) -> None:
        """10 errors in same file → 1 symbol."""
        from axm_mcp.verify import _extract_symbols

        errors = [
            {"file": "src/foo/bar.py", "line": i, "message": "...", "code": "error"}
            for i in range(10)
        ]
        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {"errors": errors},
        }
        symbols = _extract_symbols(failure)
        assert symbols == ["foo.bar"]

    def test_missing_file_key_skipped(self) -> None:
        """Error entry without 'file' key is skipped."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {"line": 7, "message": "...", "code": "error"},  # no file
                    {"file": "src/ok.py", "line": 1, "message": "...", "code": "error"},
                ]
            },
        }
        symbols = _extract_symbols(failure)
        assert symbols == ["ok"]

    def test_tests_dir_still_extracted(self) -> None:
        """Files in tests/ are still extracted as module paths."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {
                        "file": "tests/test_main.py",
                        "line": 7,
                        "message": "...",
                        "code": "error",
                    },
                ]
            },
        }
        symbols = _extract_symbols(failure)
        assert symbols == ["tests.test_main"]

    def test_empty_errors_list(self) -> None:
        """Empty errors list → empty symbols."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {"errors": []},
        }
        symbols = _extract_symbols(failure)
        assert symbols == []

    def test_no_known_prefix_in_message(self) -> None:
        """Message without known prefix → empty list."""
        from axm_mcp.verify import _extract_symbols

        failure = {
            "rule_id": "UNKNOWN_RULE",
            "message": "Some random error message",
            "details": {},
        }
        symbols = _extract_symbols(failure)
        assert symbols == []


# ── _enrich_failure tests ────────────────────────────────────────────────────


class TestEnrichFailure:
    """Tests for _enrich_failure — aggregated AST context."""

    def _make_tools(
        self, impact_results: list[ToolResult | Exception]
    ) -> dict[str, Any]:
        """Create mock tools dict with ast_impact returning given results."""
        ast_tool = MagicMock()
        ast_tool.execute.side_effect = impact_results
        return {"ast_impact": ast_tool}

    def test_aggregates_context(self) -> None:
        """Multiple symbols → aggregated context dict."""
        from axm_mcp.verify import _enrich_failure

        tools = self._make_tools(
            [
                ToolResult(
                    success=True,
                    data={
                        "callers": [{"file": "cli.py", "line": 58}],
                        "test_files": ["tests/test_bar.py"],
                        "score": 0.5,
                    },
                ),
                ToolResult(
                    success=True,
                    data={
                        "callers": [{"file": "main.py", "line": 10}],
                        "test_files": ["tests/test_baz.py"],
                        "score": 0.7,
                    },
                ),
            ]
        )

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {
                        "file": "src/foo/bar.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                    {
                        "file": "src/foo/baz.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                ]
            },
        }

        context = _enrich_failure(tools, "/tmp/proj", failure)
        assert context is not None
        assert "affected_modules" in context
        assert "callers" in context
        assert "test_files" in context
        assert "impact_score" in context
        assert context["impact_score"] == 0.7  # max

    def test_partial_ast_failure(self) -> None:
        """1 of 2 ast_impact calls fails → still returns partial context."""
        from axm_mcp.verify import _enrich_failure

        tools = self._make_tools(
            [
                ToolResult(
                    success=True,
                    data={
                        "callers": [{"file": "cli.py", "line": 58}],
                        "test_files": ["tests/test_bar.py"],
                        "score": 0.5,
                    },
                ),
                Exception("ast_impact failed"),
            ]
        )

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {
                        "file": "src/foo/bar.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                    {
                        "file": "src/foo/baz.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                ]
            },
        }

        context = _enrich_failure(tools, "/tmp/proj", failure)
        assert context is not None
        assert context["symbols_analyzed"] == 1

    def test_all_ast_fail_returns_none(self) -> None:
        """All ast_impact calls fail → returns None."""
        from axm_mcp.verify import _enrich_failure

        tools = self._make_tools(
            [
                Exception("fail 1"),
                Exception("fail 2"),
            ]
        )

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {
                        "file": "src/foo/bar.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                    {
                        "file": "src/foo/baz.py",
                        "line": 1,
                        "message": "...",
                        "code": "e",
                    },
                ]
            },
        }

        context = _enrich_failure(tools, "/tmp/proj", failure)
        assert context is None

    def test_no_ast_tool_returns_none(self) -> None:
        """No ast_impact in tools → returns None."""
        from axm_mcp.verify import _enrich_failure

        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {
                "errors": [
                    {"file": "src/foo.py", "line": 1, "message": "...", "code": "e"}
                ]
            },
        }

        context = _enrich_failure({}, "/tmp/proj", failure)
        assert context is None

    def test_no_symbols_returns_none(self) -> None:
        """No extractable symbols → returns None."""
        from axm_mcp.verify import _enrich_failure

        tools = self._make_tools([])
        failure = {
            "rule_id": "QUALITY_TYPE",
            "details": {"errors": []},
        }

        context = _enrich_failure(tools, "/tmp/proj", failure)
        assert context is None
