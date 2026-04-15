from __future__ import annotations

from typing import Any

from axm_ast.tools.search import SearchTool


def _make_suggestion(
    name: str = "get_session",
    score: float = 0.92,
    kind: str = "function",
    module: str | None = None,
) -> dict[str, Any]:
    return {"name": name, "score": score, "kind": kind, "module": module}


# --- Unit tests ---


def test_render_suggestion_line_compact() -> None:
    """module=None produces no trailing None."""
    suggestion = _make_suggestion(module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? get_session .92 func"


def test_render_suggestion_line_with_module() -> None:
    """module present is appended after kind."""
    suggestion = _make_suggestion(module="core.analyzer")
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? get_session .92 func core.analyzer"


def test_render_suggestion_line_no_padding() -> None:
    """Short name has no extra whitespace padding."""
    suggestion = _make_suggestion(name="foo", score=0.75)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? foo .75 func"


# --- Edge cases ---


def test_render_suggestion_line_long_name() -> None:
    """Very long name (31 chars) is not truncated."""
    suggestion = _make_suggestion(
        name="SearchTool._collect_module_candidates", module=None
    )
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? SearchTool._collect_module_candidates .92 func"


def test_render_suggestion_line_perfect_score() -> None:
    """Score 1.0 renders as '1.0', not '.100'."""
    suggestion = _make_suggestion(name="exact_match", score=1.0, module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? exact_match 1.0 func"


def test_render_suggestion_line_short_kind() -> None:
    """Kind shorter than 4 chars rendered as-is, no padding."""
    suggestion = _make_suggestion(name="foo", kind="cls", module=None)
    line = SearchTool._render_suggestion_line(suggestion)
    assert line == "? foo .92 cls"
