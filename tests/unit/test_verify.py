"""Unit tests for :mod:`axm_mcp.verify`.

Merged from aspect-split mirror sources:
- test_verify.py            (verify_project orchestration)
- test_verify_enrichment.py (_enrich_failure scoring)
- test_verify_tool.py       (VerifyTool ToolResult contract)
- test_coverage_gaps.py     (VerifyTool.execute path delegation, _run_tool error paths)

Helper namespacing: ``FakeTool`` / ``FakeToolResult`` are the coverage-gap
stand-ins (used by the _run_tool error-path tests); the enrichment fixture
keeps its own ``_FakeResult`` dataclass and ``_make_tools`` factory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from axm.tools.base import AXMTool, ToolResult

from axm_mcp.verify import VerifyTool, _enrich_failure, _run_tool

# ─────────────────────────────── helpers ─────────────────────────────────────


@dataclass
class FakeToolResult:
    """Minimal ToolResult stand-in."""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class FakeTool:
    """Minimal ToolLike stand-in for testing tool dispatch."""

    def __init__(
        self,
        name: str = "fake_tool",
        *,
        result: FakeToolResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._name = name
        self._result = result or FakeToolResult(data={"key": "val"})
        self._raise_exc = raise_exc

    @property
    def name(self) -> str:
        return self._name

    def execute(self, **kwargs: Any) -> FakeToolResult:
        """Execute the fake tool."""
        if self._raise_exc:
            raise self._raise_exc
        return self._result


# --- verify_project orchestration ---


class TestVerifyToolRegistered:
    """Verify tool must be discoverable on the MCP server."""

    def test_verify_function_importable(self) -> None:
        """verify_project should be importable from axm_mcp.verify."""
        from axm_mcp.verify import verify_project

        assert callable(verify_project)


class TestVerifyProject:
    """Tests for verify_project() orchestration logic."""

    @pytest.fixture()
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


# --- _enrich_failure scoring ---


@dataclass
class _FakeResult:
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)


@pytest.fixture
def _make_tools():
    """Return a factory that builds a tools dict with a mock ast_impact."""

    def _factory(side_effects: list[_FakeResult]) -> dict[str, Any]:
        mock_tool = MagicMock()
        mock_tool.execute = MagicMock(side_effect=side_effects)
        return {"ast_impact": mock_tool}

    return _factory


def test_enrich_failure_score_is_string(_make_tools, monkeypatch):
    """Score returned by ast_impact is a string — preserve it as-is."""
    monkeypatch.setattr(
        "axm_mcp.verify._extract_symbols",
        lambda _f: ["some_func"],
    )
    tools = _make_tools(
        [
            _FakeResult(
                success=True, data={"score": "HIGH", "callers": [], "test_files": []}
            ),
        ]
    )

    ctx = _enrich_failure(tools, "/project", {"rule": "E001"})

    assert ctx is not None
    assert ctx["impact_score"] == "HIGH"


def test_enrich_failure_max_score_multiple_symbols(_make_tools, monkeypatch):
    """With 3 symbols returning LOW, HIGH, MEDIUM the max must be HIGH."""
    monkeypatch.setattr(
        "axm_mcp.verify._extract_symbols",
        lambda _f: ["sym_a", "sym_b", "sym_c"],
    )
    tools = _make_tools(
        [
            _FakeResult(
                success=True, data={"score": "LOW", "callers": [], "test_files": []}
            ),
            _FakeResult(
                success=True, data={"score": "HIGH", "callers": [], "test_files": []}
            ),
            _FakeResult(
                success=True, data={"score": "MEDIUM", "callers": [], "test_files": []}
            ),
        ]
    )

    ctx = _enrich_failure(tools, "/project", {"rule": "E001"})

    assert ctx is not None
    assert ctx["impact_score"] == "HIGH"


def test_enrich_failure_unknown_score_graceful(_make_tools, monkeypatch):
    """An unexpected score value like CRITICAL must not crash enrichment."""
    monkeypatch.setattr(
        "axm_mcp.verify._extract_symbols",
        lambda _f: ["some_func"],
    )
    tools = _make_tools(
        [
            _FakeResult(
                success=True,
                data={"score": "CRITICAL", "callers": [], "test_files": []},
            ),
        ]
    )

    ctx = _enrich_failure(tools, "/project", {"rule": "E001"})

    assert ctx is not None
    # CRITICAL is outside the ordinal map (LOW<MEDIUM<HIGH); it must be ignored
    # and the aggregate score fall back to LOW rather than crash.
    assert ctx["impact_score"] == "LOW"
    assert ctx["symbols_analyzed"] == 1


def test_enrich_failure_empty_score_falls_back_to_low(_make_tools, monkeypatch):
    """When score is None, enrichment falls back to LOW."""
    monkeypatch.setattr(
        "axm_mcp.verify._extract_symbols",
        lambda _f: ["some_func"],
    )
    tools = _make_tools(
        [
            _FakeResult(success=True, data={"callers": [], "test_files": []}),
        ]
    )

    ctx = _enrich_failure(tools, "/project", {"rule": "E001"})

    assert ctx is not None
    assert ctx["impact_score"] == "LOW"


def test_enrich_failure_single_symbol_uses_its_score(_make_tools, monkeypatch):
    """With a single symbol the impact_score equals that symbol's score."""
    monkeypatch.setattr(
        "axm_mcp.verify._extract_symbols",
        lambda _f: ["only_func"],
    )
    tools = _make_tools(
        [
            _FakeResult(
                success=True, data={"score": "MEDIUM", "callers": [], "test_files": []}
            ),
        ]
    )

    ctx = _enrich_failure(tools, "/project", {"rule": "E001"})

    assert ctx is not None
    assert ctx["impact_score"] == "MEDIUM"


# --- VerifyTool ToolResult contract ---


def _audit_tool() -> MagicMock:
    tool = MagicMock()
    tool.execute.return_value = ToolResult(
        success=True,
        data={
            "score": 80,
            "grade": "B",
            "passed": ["ok1", "ok2"],
            "failed": [
                {
                    "rule_id": "QUALITY_TYPE",
                    "message": "5 errors",
                    "text": "• untested: foo.py",
                    "fix_hint": "Add type hints",
                }
            ],
        },
    )
    return tool


def _init_tool() -> MagicMock:
    tool = MagicMock()
    tool.execute.return_value = ToolResult(
        success=True,
        data={"score": 100, "grade": "A", "passed_count": 3, "failed": []},
    )
    return tool


class TestVerifyTool:
    def test_name(self) -> None:
        assert VerifyTool().name == "verify"

    def test_execute_returns_tool_result(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert isinstance(result, ToolResult)
        assert result.success is True

    def test_execute_data_preserved(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert "audit" in result.data
        assert "governance" in result.data
        assert result.data["audit"]["grade"] == "B"

    def test_execute_text_non_null_and_compact(self) -> None:
        tools: dict[str, Any] = {"audit": _audit_tool(), "init_check": _init_tool()}
        result = VerifyTool(tools).execute(path="/tmp/fake")
        assert result.text is not None
        assert result.text.startswith("verify | audit B 80")
        assert "✗ QUALITY_TYPE" in result.text

    def test_execute_with_no_tools(self) -> None:
        result = VerifyTool({}).execute(path="/tmp/fake")
        assert result.success is True
        assert result.data["audit"] is None
        assert result.data["governance"] is None
        assert result.text is not None
        assert "audit: skipped" in result.text


# --- VerifyTool.execute path delegation ---


class TestVerifyToolExecute:
    """Cover VerifyTool.execute path delegation."""

    def test_path_forwarded_to_verify_project(self) -> None:
        """Explicit path is forwarded to verify_project as a string."""
        with patch("axm_mcp.verify.verify_project") as mock_vp:
            mock_vp.return_value = {"audit": None, "governance": None}

            VerifyTool({}).execute(path="/tmp/proj")
            assert mock_vp.call_args[0][0] == "/tmp/proj"

    def test_default_path_is_dot(self) -> None:
        """When no path is given, defaults to '.'."""
        with patch("axm_mcp.verify.verify_project") as mock_vp:
            mock_vp.return_value = {"audit": None, "governance": None}

            VerifyTool({}).execute()
            assert mock_vp.call_args[0][0] == "."


# --- _run_tool error paths ---


class TestRunToolErrorPaths:
    """Cover _run_tool failure/exception (verify.py:68-72)."""

    def test_tool_failure_returns_error(self) -> None:
        """When tool.execute returns success=False, return error dict."""
        tool = FakeTool(
            result=FakeToolResult(success=False, error="audit failed"),
        )
        result = _run_tool(
            cast(Mapping[str, AXMTool], {"audit": tool}), "audit", path="."
        )
        assert result == {"error": "audit failed"}

    def test_tool_exception_returns_error(self) -> None:
        """When tool.execute raises, catch and return error dict."""
        tool = FakeTool(raise_exc=RuntimeError("boom"))
        result = _run_tool(
            cast(Mapping[str, AXMTool], {"audit": tool}), "audit", path="."
        )
        assert result is not None
        assert "boom" in result["error"]
