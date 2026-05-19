"""Tests for SourceBodyHook."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_ast.hooks.source_body import SourceBodyHook
from tests.integration._helpers import _ANALYZER, _make_mock_mod


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


class TestHookOnRealPackage:
    """Integration test on axm-ast itself."""

    def test_hook_on_real_package(self) -> None:
        """Extract ImpactHook body from axm-ast source."""
        src_path = Path(__file__).resolve().parent.parent.parent / "src" / "axm_ast"
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


def _make_mock_fn(name: str, start: int, end: int) -> MagicMock:
    """Create a mock function symbol."""
    fn = MagicMock()
    fn.name = name
    fn.line_start = start
    fn.line_end = end
    return fn


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
        mock_search.return_value = [("example", mock_fn)]
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
                return [("alpha", mock_fn_a)]
            if name == "func_b":
                return [("beta", mock_fn_b)]
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
                return [("file1", mock_fn_a)]
            if name == "func_b":
                return [("file2", mock_fn_b)]
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
        mock_search.return_value = [("example", mock_fn)]
        mock_find.return_value = mock_mod

        hook = SourceBodyHook()
        result = hook.execute({}, symbol="my_func", path=str(tmp_path))

        assert result.success
        symbols = result.metadata["symbols"]
        assert "start_line" not in symbols
        assert "end_line" not in symbols


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
                return [("models", mock_cls)]
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


# ── Real-fixture dotted resolution (migrated from test_resolve_dotted.py) ──
#
# These tests drive ``SourceBodyHook.execute`` against real fixture packages
# built on disk (no mocks). They cover deeply-nested classes, missing class /
# missing member paths, and module-level function resolution — originally
# reaching through the private ``_resolve_dotted`` helper.


@pytest.fixture()
def nested_class_pkg(tmp_path: Path) -> Path:
    """Real package with deeply nested classes: ``Outer.Inner.method``."""
    src = tmp_path / "nested_pkg"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "deep.py").write_text(
        """\
class Outer:
    class Inner:
        def method(self):
            return 42
"""
    )
    return src


@pytest.fixture()
def module_func_pkg(tmp_path: Path) -> Path:
    """Real package with a module-level function: ``helpers.top_level_func``."""
    src = tmp_path / "modfunc_pkg"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "helpers.py").write_text(
        """\
def top_level_func():
    return "hello"
"""
    )
    return src


class TestDeeplyNestedDottedPath:
    """``Outer.Inner.method`` — best-effort resolution via public hook."""

    def test_deeply_nested_resolves_or_reports_not_found(
        self, nested_class_pkg: Path
    ) -> None:
        hook = SourceBodyHook()
        result = hook.execute(
            {}, symbol="Outer.Inner.method", path=str(nested_class_pkg)
        )

        # Hook always returns success; resolution is best-effort. The output
        # markdown either contains the method body or an explicit not-found
        # note — both prove the nested path was attempted without crashing.
        assert result.success
        rendered = result.metadata["symbols"]
        assert isinstance(rendered, str)
        assert "Outer.Inner.method" in rendered or "def method" in rendered


class TestDottedNonExistentSymbol:
    """Missing class / missing member — surfaced as not-found, no crash."""

    def test_fake_class_returns_not_found(self, nested_class_pkg: Path) -> None:
        hook = SourceBodyHook()
        result = hook.execute(
            {}, symbol="FakeClass.fake_method", path=str(nested_class_pkg)
        )
        assert result.success
        rendered = result.metadata["symbols"]
        assert isinstance(rendered, str)
        assert "not found" in rendered.lower()

    def test_real_class_fake_member_returns_not_found(
        self, nested_class_pkg: Path
    ) -> None:
        hook = SourceBodyHook()
        result = hook.execute(
            {}, symbol="Outer.nonexistent", path=str(nested_class_pkg)
        )
        assert result.success
        rendered = result.metadata["symbols"]
        assert isinstance(rendered, str)
        assert "not found" in rendered.lower()


class TestModuleLevelFunction:
    """``module.top_level_func`` — resolves via module-path branch."""

    def test_module_dot_func_resolves(self, module_func_pkg: Path) -> None:
        hook = SourceBodyHook()
        result = hook.execute(
            {}, symbol="helpers.top_level_func", path=str(module_func_pkg)
        )
        assert result.success
        rendered = result.metadata["symbols"]
        assert isinstance(rendered, str)
        assert "def top_level_func" in rendered
        assert "helpers.py" in rendered

    def test_module_dot_missing_func_returns_not_found(
        self, module_func_pkg: Path
    ) -> None:
        hook = SourceBodyHook()
        result = hook.execute(
            {}, symbol="helpers.no_such_func", path=str(module_func_pkg)
        )
        assert result.success
        rendered = result.metadata["symbols"]
        assert isinstance(rendered, str)
        assert "not found" in rendered.lower()
