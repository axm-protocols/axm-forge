"""Integration tests for SearchTool (real I/O via public tool surface)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_ast.tools.search import SearchTool


def _make_func(name: str, kind_value: str = "function") -> MagicMock:
    fn = MagicMock()
    fn.name = name
    fn.kind = MagicMock()
    fn.kind.value = kind_value
    fn.return_type = None
    fn.parameters = []
    fn.decorators = []
    fn.docstring = None
    return fn


def _suggestion(name: str, score: float, kind: str, module: str) -> dict[str, Any]:
    return {"name": name, "score": score, "kind": kind, "module": module}


class TestSearchWithSuggestions:
    """Functional tests for suggestions wired into ast_search."""

    def test_search_with_suggestions_text(self, tmp_path: Path) -> None:
        """Zero results + suggestions produces header and ?-prefixed lines (AC5)."""
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
            _suggestion("get_sessions", 0.85, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search.find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool().execute(path=str(tmp_path), name="get_sesion")

        assert result.text is not None
        assert "suggestion" in result.text.lower()
        lines = result.text.strip().splitlines()
        suggestion_lines = [ln for ln in lines if ln.startswith("?")]
        assert len(suggestion_lines) >= 2

    def test_search_with_results_no_suggestions(self, tmp_path: Path) -> None:
        """When results exist, no suggestions key in data (AC3)."""
        func = _make_func("search_symbols")
        with patch(
            "axm_ast.core.analyzer.search_symbols",
            return_value=[("core.analyzer", func)],
        ):
            result = SearchTool().execute(path=str(tmp_path), name="search")

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_no_name_no_suggestions(self, tmp_path: Path) -> None:
        """When name is None and no results, no suggestions key (AC4)."""
        with patch("axm_ast.core.analyzer.search_symbols", return_value=[]):
            result = SearchTool().execute(path=str(tmp_path))

        assert "results" in result.data
        assert "suggestions" not in result.data

    def test_search_suggestions_data_shape(self, tmp_path: Path) -> None:
        """Suggestions data has correct shape alongside empty results (AC4)."""
        suggestions = [
            _suggestion("get_session", 0.92, "function", "core.analyzer"),
        ]
        with (
            patch("axm_ast.core.analyzer.search_symbols", return_value=[]),
            patch(
                "axm_ast.tools.search.find_suggestions",
                return_value=suggestions,
            ),
        ):
            result = SearchTool().execute(path=str(tmp_path), name="get_sesion")

        assert result.data["results"] == []
        assert "suggestions" in result.data
        assert isinstance(result.data["suggestions"], list)
        for s in result.data["suggestions"]:
            assert "name" in s
            assert "score" in s
            assert "kind" in s
            assert "module" in s


class TestSearchResultNoCountKeyIntegration:
    """Integration-scope sibling: empty-result path."""

    @patch.object(SearchTool, "format_symbol", return_value={"name": "X"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_empty_results_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty search results should return data={'results': []} with no count key."""
        mock_search.return_value = []

        result = SearchTool().execute(path=str(tmp_path), name="NonExistent")

        assert result.success is True
        assert result.data == {"results": []}
        assert "count" not in result.data
