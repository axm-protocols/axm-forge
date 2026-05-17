"""Unit tests for SourceBodyHook."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_ast.hooks.source_body import SourceBodyHook
from tests.unit._helpers import _ANALYZER


class TestSourceBodyMissingPath:
    """Invalid path handling."""

    def test_source_body_missing_path(self) -> None:
        """Invalid path returns HookResult.fail with clear message."""
        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


class TestSourceBodyMissingParam:
    """Missing required param."""

    def test_missing_symbol_param(self) -> None:
        """Fail when 'symbol' param is missing."""
        hook = SourceBodyHook()
        result = hook.execute({})
        assert not result.success
        assert result.error is not None
        assert "symbol" in result.error


class TestSourceBodyMissingSymbol:
    """Missing symbol handling — no crash, body=null."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_missing_symbol(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Unknown symbol returns body=None with error message."""
        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="nonexistent", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "nonexistent" in data


class TestSourceBodyDottedNotFound:
    """Dotted symbol: not found returns error."""

    @patch(f"{_ANALYZER}.search_symbols", return_value=[])
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_dotted_not_found(
        self,
        mock_analyze: MagicMock,
        _mock_search: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Foo.nonexistent returns error dict with body=None."""
        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="Foo.nonexistent", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "not found" in data.lower() or "error" in data.lower()


class TestEntryPointDiscoverable:
    """Entry point registration test."""

    def test_entry_point_discoverable(self) -> None:
        """'ast:source-body' is registered in axm.hooks entry points."""
        from importlib.metadata import entry_points

        hooks = entry_points(group="axm.hooks")
        names = [ep.name for ep in hooks]
        assert "ast:source-body" in names
