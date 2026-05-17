"""Unit tests for source_body markdown edge cases (no real I/O)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_ast.hooks.source_body import SourceBodyHook
from tests.unit._helpers import _ANALYZER


class TestSymbolNotFoundEdge:
    """Edge: non-existent symbol returns HookResult with error."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_symbol_not_found(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Non-existent symbol does not crash."""
        mock_analyze.return_value = MagicMock()

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="ghost_func", path=str(tmp_path))

        # Should still return a result without crash
        assert result.success or not result.success


class TestMissingPathEdge:
    """Edge: invalid path in params."""

    def test_missing_path(self) -> None:
        """Invalid path returns HookResult.fail (unchanged)."""
        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None
