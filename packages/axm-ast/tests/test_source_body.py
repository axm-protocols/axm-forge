"""Tests for SourceBodyHook."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.source_body import SourceBodyHook

# ── Unit tests ─────────────────────────────────────────────────────

_ANALYZER = "axm_ast.core.analyzer"


class TestSourceBodySingleSymbol:
    """Single symbol extraction."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_single_symbol(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns file, start_line, end_line, body for a single symbol."""
        src = tmp_path / "example.py"
        src.write_text("line1\ndef my_func():\n    pass\nline4\n")

        mock_fn = MagicMock()
        mock_fn.name = "my_func"
        mock_fn.line_start = 2
        mock_fn.line_end = 3

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_search.return_value = [mock_fn]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_func", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert data["file"] == "example.py"
        assert data["start_line"] == 2
        assert data["end_line"] == 3
        assert "def my_func():" in data["body"]
        assert "    pass" in data["body"]


class TestSourceBodyMultiSymbol:
    """Multi-symbol (newline-separated) extraction."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_multi_symbol(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Newline-separated symbols return a list with 2 entries."""
        src = tmp_path / "mod.py"
        src.write_text("def func_a():\n    pass\ndef func_b():\n    return 1\n")

        mock_fn_a = MagicMock()
        mock_fn_a.name = "func_a"
        mock_fn_a.line_start = 1
        mock_fn_a.line_end = 2

        mock_fn_b = MagicMock()
        mock_fn_b.name = "func_b"
        mock_fn_b.line_start = 3
        mock_fn_b.line_end = 4

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        def fake_search(pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "func_a":
                return [mock_fn_a]
            if name == "func_b":
                return [mock_fn_b]
            return []

        mock_search.side_effect = fake_search
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="func_a\nfunc_b", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, list)
        assert len(symbols) == 2
        assert symbols[0]["symbol"] == "func_a"
        assert symbols[1]["symbol"] == "func_b"
        assert "def func_a():" in symbols[0]["body"]
        assert "return 1" in symbols[1]["body"]


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
        assert data["body"] is None
        assert "error" in data
        assert "nonexistent" in data["error"]


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


# ── Functional tests ───────────────────────────────────────────────


class TestEntryPointDiscoverable:
    """Entry point registration test."""

    def test_entry_point_discoverable(self) -> None:
        """'ast:source-body' is registered in axm.hooks entry points."""
        from importlib.metadata import entry_points

        hooks = entry_points(group="axm.hooks")
        names = [ep.name for ep in hooks]
        assert "ast:source-body" in names


class TestHookOnRealPackage:
    """Integration test on axm-ast itself."""

    def test_hook_on_real_package(self) -> None:
        """Extract ImpactHook body from axm-ast source."""
        src_path = Path(__file__).resolve().parent.parent / "src" / "axm_ast"
        if not src_path.is_dir():
            pytest.skip("axm-ast source not found at expected path")

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="ImpactHook", path=str(src_path))

        assert result.success
        data = result.metadata["symbols"]
        assert data["body"] is not None
        assert "class ImpactHook" in data["body"]
        assert data["file"] == "hooks/impact.py"
        assert isinstance(data["start_line"], int)
        assert isinstance(data["end_line"], int)
        assert data["start_line"] < data["end_line"]
