from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.search import SearchTool


@pytest.fixture
def _mock_pkg():
    return MagicMock()


class TestSearchResultNoCountKey:
    """Verify that _search does not include a 'count' key in result.data."""

    @patch.object(SearchTool, "_format_symbol", return_value={"name": "Foo"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_result_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        _mock_pkg: MagicMock,
    ) -> None:
        """Run a search and assert 'count' is not in result.data."""
        mock_search.return_value = [("mod", MagicMock())]

        result = SearchTool._search(
            _mock_pkg, name="Foo", returns=None, kind=None, inherits=None
        )

        assert result.success is True
        assert "count" not in result.data
        assert "results" in result.data
        assert len(result.data["results"]) == 1

    @patch.object(SearchTool, "_format_symbol", return_value={"name": "X"})
    @patch("axm_ast.core.analyzer.search_symbols")
    def test_search_empty_results_no_count_key(
        self,
        mock_search: MagicMock,
        mock_fmt: MagicMock,
        _mock_pkg: MagicMock,
    ) -> None:
        """Empty search results should return data={'results': []} with no count key."""
        mock_search.return_value = []

        result = SearchTool._search(
            _mock_pkg, name="NonExistent", returns=None, kind=None, inherits=None
        )

        assert result.success is True
        assert result.data == {"results": []}
        assert "count" not in result.data
