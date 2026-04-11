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
        mock_search.return_value = [("example", mock_fn)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_func", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "example.py" in data
        assert "```python" in data
        assert "def my_func():" in data
        assert "    pass" in data
        assert "start_line" not in data
        assert "end_line" not in data


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
                return [("mod", mock_fn_a)]
            if name == "func_b":
                return [("mod", mock_fn_b)]
            return []

        mock_search.side_effect = fake_search
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="func_a\nfunc_b", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert isinstance(symbols, str)
        assert "def func_a():" in symbols
        assert "return 1" in symbols
        assert "```python" in symbols
        assert "mod.py" in symbols


class TestSourceBodyVariable:
    """Variable/constant resolution in source_body hook."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_resolves_variable(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns file, line, value_repr, body for a module-level constant."""
        from axm_ast.models.nodes import VariableInfo

        src = tmp_path / "consts.py"
        src.write_text("_TOLERANCE: float = 0.01\nMAX = 100\n")

        mock_var = VariableInfo(
            name="_TOLERANCE", annotation="float", value_repr="0.01", line=1
        )

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_search.return_value = [("consts", mock_var)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="_TOLERANCE", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "consts.py" in data
        assert "_TOLERANCE" in data
        assert "value_repr" in data or "0.01" in data
        assert "```python" in data


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


# ── Dotted symbol tests ────────────────────────────────────────────


class TestSourceBodyDottedClassMethod:
    """Dotted symbol: ClassName.method resolution."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_dotted_class_method(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """ClassName.method returns body with correct file, start_line, end_line."""
        src = tmp_path / "models.py"
        src.write_text("class MyClass:\n    def do_work(self) -> None:\n        pass\n")

        mock_method = MagicMock()
        mock_method.name = "do_work"
        mock_method.line_start = 2
        mock_method.line_end = 3

        mock_cls = MagicMock()
        mock_cls.name = "MyClass"
        mock_cls.methods = [mock_method]

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg

        # search_symbols won't find "MyClass.do_work" as a flat name,
        # but should find "MyClass" when the dotted path is split.
        def fake_search(pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "MyClass":
                return [("models", mock_cls)]
            return []

        mock_search.side_effect = fake_search
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="MyClass.do_work", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "models.py" in data
        assert "```python" in data
        assert "def do_work" in data


class TestSourceBodyDottedModuleSymbol:
    """Dotted symbol: module.function resolution."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_dotted_module_symbol(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """module.function returns body correctly for module-level symbol."""
        src = tmp_path / "utils.py"
        src.write_text("def helper():\n    return 42\n")

        mock_fn = MagicMock()
        mock_fn.name = "helper"
        mock_fn.line_start = 1
        mock_fn.line_end = 2

        mock_mod = MagicMock()
        mock_mod.path = src
        mock_mod.name = "utils"

        mock_pkg = MagicMock()
        mock_pkg.modules = {"utils": mock_mod}
        mock_analyze.return_value = mock_pkg

        # When split as module.function, search in the resolved module.
        def fake_search(pkg: Any, name: str | None, **_kw: Any) -> list[Any]:
            if name == "helper":
                return [("utils", mock_fn)]
            return []

        mock_search.side_effect = fake_search
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="utils.helper", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "utils.py" in data
        assert "```python" in data
        assert "def helper" in data


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


class TestSourceBodySimpleNameUnchanged:
    """Simple (non-dotted) name: existing behavior preserved."""

    @patch(f"{_ANALYZER}.find_module_for_symbol")
    @patch(f"{_ANALYZER}.search_symbols")
    @patch(f"{_ANALYZER}.analyze_package")
    def test_source_body_simple_name_unchanged(
        self,
        mock_analyze: MagicMock,
        mock_search: MagicMock,
        mock_find: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A plain name (no dot) resolves exactly as before."""
        src = tmp_path / "plain.py"
        src.write_text("def my_function():\n    return True\n")

        mock_fn = MagicMock()
        mock_fn.name = "my_function"
        mock_fn.line_start = 1
        mock_fn.line_end = 2

        mock_mod = MagicMock()
        mock_mod.path = src

        mock_pkg = MagicMock()
        mock_analyze.return_value = mock_pkg
        mock_search.return_value = [("plain", mock_fn)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_function", path=str(tmp_path))

        assert result.success
        data = result.metadata["symbols"]
        assert isinstance(data, str)
        assert "plain.py" in data
        assert "```python" in data
        assert "def my_function" in data


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
        assert isinstance(data, str)
        assert "class ImpactHook" in data
        assert "hooks/impact.py" in data
        assert "```python" in data
