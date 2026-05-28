from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_mcp.verify import _enrich_failure


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


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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
