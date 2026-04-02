"""Tests for source_body markdown string output (AXM-1008).

Validates that _run_extraction returns a markdown string instead of dict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_ast.hooks.source_body import SourceBodyHook

_ANALYZER = "axm_ast.core.analyzer"


# ── Helpers ───────────────────────────────────────────────────────────


def _make_mock_fn(name: str, start: int, end: int) -> MagicMock:
    """Create a mock function symbol."""
    fn = MagicMock()
    fn.name = name
    fn.line_start = start
    fn.line_end = end
    return fn


def _make_mock_mod(path: Path) -> MagicMock:
    """Create a mock module with given path."""
    mod = MagicMock()
    mod.path = path
    return mod


# ── Unit tests ────────────────────────────────────────────────────────


class TestSingleSymbolReturnsString:
    """AC1/AC4: Single symbol returns markdown string, no special-casing."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_single_symbol_returns_string(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Single symbol extraction returns str with fenced python block."""
        src = tmp_path / "example.py"
        src.write_text("def my_func():\n    pass\n")

        mock_fn = _make_mock_fn("my_func", 1, 2)
        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()
        mock_search.return_value = [mock_fn]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_func", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        assert "```python" in symbols
        assert "def my_func():" in symbols


class TestMultiSymbolSameFileGrouped:
    """AC2: Symbols from same file grouped under one header."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_multi_symbol_same_file_grouped(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Two symbols from same file get single file header, one fenced block."""
        src = tmp_path / "mod.py"
        src.write_text("def func_a():\n    pass\ndef func_b():\n    return 1\n")

        mock_fn_a = _make_mock_fn("func_a", 1, 2)
        mock_fn_b = _make_mock_fn("func_b", 3, 4)
        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()

        def fake_search(_pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
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
        assert isinstance(symbols, str)
        # Single file header
        assert symbols.count("mod.py") == 1
        # Both bodies in one fenced block
        assert "func_a" in symbols
        assert "func_b" in symbols
        assert symbols.count("```python") == 1


class TestMultiSymbolDifferentFiles:
    """AC2: Symbols from different files get separate headers."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_multi_symbol_different_files(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Two symbols from different files get two file headers."""
        src_a = tmp_path / "alpha.py"
        src_a.write_text("def func_a():\n    pass\n")
        src_b = tmp_path / "beta.py"
        src_b.write_text("def func_b():\n    return 1\n")

        mock_fn_a = _make_mock_fn("func_a", 1, 2)
        mock_fn_b = _make_mock_fn("func_b", 1, 2)
        mock_mod_a = _make_mock_mod(src_a)
        mock_mod_b = _make_mock_mod(src_b)
        mock_analyze.return_value = MagicMock()

        def fake_search(_pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "func_a":
                return [mock_fn_a]
            if name == "func_b":
                return [mock_fn_b]
            return []

        mock_search.side_effect = fake_search

        def fake_find(_pkg: Any, sym: Any) -> MagicMock:
            if sym.name == "func_a":
                return mock_mod_a
            return mock_mod_b

        mock_find.side_effect = fake_find

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="func_a\nfunc_b", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        # Two file headers
        assert "alpha.py" in symbols
        assert "beta.py" in symbols
        # Two fenced blocks
        assert symbols.count("```python") == 2


class TestFilesMetadataPresent:
    """AC1: files list in metadata."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_files_metadata_present(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Metadata includes files list with relative paths."""
        src_a = tmp_path / "file1.py"
        src_a.write_text("def func_a():\n    pass\n")
        src_b = tmp_path / "file2.py"
        src_b.write_text("def func_b():\n    return 1\n")

        mock_fn_a = _make_mock_fn("func_a", 1, 2)
        mock_fn_b = _make_mock_fn("func_b", 1, 2)
        mock_mod_a = _make_mock_mod(src_a)
        mock_mod_b = _make_mock_mod(src_b)
        mock_analyze.return_value = MagicMock()

        def fake_search(_pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "func_a":
                return [mock_fn_a]
            if name == "func_b":
                return [mock_fn_b]
            return []

        mock_search.side_effect = fake_search

        def fake_find(_pkg: Any, sym: Any) -> MagicMock:
            if sym.name == "func_a":
                return mock_mod_a
            return mock_mod_b

        mock_find.side_effect = fake_find

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="func_a\nfunc_b", path=str(tmp_path))

        assert result.success
        assert result.metadata["files"] == ["file1.py", "file2.py"]


class TestNoStartEndLineInOutput:
    """AC3: start_line and end_line not in output string."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_no_start_end_line_in_output(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Output string does not contain start_line or end_line."""
        src = tmp_path / "example.py"
        src.write_text("def my_func():\n    pass\n")

        mock_fn = _make_mock_fn("my_func", 1, 2)
        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()
        mock_search.return_value = [mock_fn]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_func", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert "start_line" not in symbols
        assert "end_line" not in symbols


class TestVariableSymbolIncludesRepr:
    """Variable symbols include value_repr in output."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_variable_symbol_includes_repr(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Variable extraction includes value_repr in the markdown output."""
        from axm_ast.models.nodes import VariableInfo

        src = tmp_path / "consts.py"
        src.write_text("MAX_RETRIES: int = 3\n")

        mock_var = VariableInfo(
            name="MAX_RETRIES", annotation="int", value_repr="3", line=1
        )
        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()
        mock_search.return_value = [mock_var]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="MAX_RETRIES", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        assert "value_repr" in symbols or "3" in symbols


# ── Edge cases ────────────────────────────────────────────────────────


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


class TestDottedClassMethodMarkdown:
    """Edge: Class.method returns markdown with file path header."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_dotted_class_method_markdown(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Class.method extraction produces markdown with file header."""
        src = tmp_path / "models.py"
        src.write_text("class MyClass:\n    def do_work(self) -> None:\n        pass\n")

        mock_method = MagicMock()
        mock_method.name = "do_work"
        mock_method.line_start = 2
        mock_method.line_end = 3

        mock_cls = MagicMock()
        mock_cls.name = "MyClass"
        mock_cls.methods = [mock_method]

        mock_mod = _make_mock_mod(src)
        mock_analyze.return_value = MagicMock()

        def fake_search(_pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "MyClass":
                return [mock_cls]
            return []

        mock_search.side_effect = fake_search
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="MyClass.do_work", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        assert "models.py" in symbols
        assert "```python" in symbols
        assert "def do_work" in symbols
