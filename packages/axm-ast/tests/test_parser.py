"""Test tree-sitter parser — unit and functional tests.

Tests cover: basic parsing, module extraction, edge cases
(empty files, syntax errors, complex decorators, async, __all__).
"""

from pathlib import Path

import pytest

from axm_ast.core.parser import (
    extract_module_info,
    parse_file,
    parse_source,
)
from axm_ast.models.nodes import FunctionKind

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ─── parse_source ────────────────────────────────────────────────────────────


class TestParseSource:
    """Tests for parse_source()."""

    def test_simple_function(self):
        tree = parse_source("def foo(): pass")
        assert tree.root_node.type == "module"

    def test_empty_string(self):
        tree = parse_source("")
        assert tree.root_node.type == "module"

    def test_syntax_error_graceful(self):
        """Tree-sitter should parse even with syntax errors."""
        tree = parse_source("def broken(")
        assert tree.root_node.has_error is True

    def test_multiline_function(self):
        src = (
            "def add(a: int, b: int) -> int:\n"
            '    """Add two numbers."""\n'
            "    return a + b"
        )
        tree = parse_source(src)
        assert tree.root_node.child_count > 0


# ─── parse_file ──────────────────────────────────────────────────────────────


class TestParseFile:
    """Tests for parse_file()."""

    def test_parse_valid_file(self):
        tree = parse_file(SAMPLE_PKG / "__init__.py")
        assert tree.root_node.type == "module"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_file(Path("/nonexistent/path.py"))

    def test_not_python_file(self, tmp_path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="Not a Python file"):
            parse_file(txt)

    def test_empty_file(self):
        tree = parse_file(FIXTURES / "empty.py")
        assert tree.root_node.type == "module"

    def test_broken_file(self):
        """Broken syntax should still parse (graceful degradation)."""
        tree = parse_file(FIXTURES / "broken.py")
        assert tree.root_node.has_error is True


# ─── extract_module_info — functions ─────────────────────────────────────────


class TestExtractFunctions:
    """Tests for function extraction."""

    def test_extracts_public_function(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        names = [f.name for f in mod.functions]
        assert "greet" in names

    def test_extracts_private_function(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        names = [f.name for f in mod.functions]
        assert "_internal_helper" in names

    def test_function_params(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        greet = next(f for f in mod.functions if f.name == "greet")
        assert len(greet.params) == 1
        assert greet.params[0].name == "name"
        assert greet.params[0].annotation == "str"
        assert greet.params[0].default == '"world"'

    def test_function_return_type(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        greet = next(f for f in mod.functions if f.name == "greet")
        assert greet.return_type == "str"

    def test_function_docstring(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        greet = next(f for f in mod.functions if f.name == "greet")
        assert greet.docstring is not None
        assert "greeting" in greet.docstring.lower()

    def test_async_function(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        fetch = next((f for f in mod.functions if f.name == "fetch_data"), None)
        assert fetch is not None
        # Note: tree-sitter may handle async differently
        # We check the function was extracted at minimum
        assert fetch.return_type is not None

    def test_function_line_range(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        greet = next(f for f in mod.functions if f.name == "greet")
        assert greet.line_start > 0
        assert greet.line_end >= greet.line_start


# ─── extract_module_info — classes ───────────────────────────────────────────


class TestExtractClasses:
    """Tests for class extraction."""

    def test_extracts_public_class(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        names = [c.name for c in mod.classes]
        assert "Calculator" in names

    def test_extracts_private_class(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        names = [c.name for c in mod.classes]
        assert "_InternalClass" in names

    def test_class_docstring(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        calc = next(c for c in mod.classes if c.name == "Calculator")
        assert calc.docstring is not None
        assert "calculator" in calc.docstring.lower()

    def test_class_methods_extracted(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        calc = next(c for c in mod.classes if c.name == "Calculator")
        method_names = [m.name for m in calc.methods]
        assert "__init__" in method_names
        assert "add" in method_names

    def test_property_method(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        calc = next(c for c in mod.classes if c.name == "Calculator")
        name_method = next((m for m in calc.methods if m.name == "name"), None)
        assert name_method is not None
        assert name_method.kind == FunctionKind.PROPERTY

    def test_staticmethod(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        calc = next(c for c in mod.classes if c.name == "Calculator")
        version = next((m for m in calc.methods if m.name == "version"), None)
        assert version is not None
        assert version.kind == FunctionKind.STATICMETHOD

    def test_classmethod(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        calc = next(c for c in mod.classes if c.name == "Calculator")
        from_cfg = next((m for m in calc.methods if m.name == "from_config"), None)
        assert from_cfg is not None
        assert from_cfg.kind == FunctionKind.CLASSMETHOD


# ─── extract_module_info — imports ───────────────────────────────────────────


class TestExtractImports:
    """Tests for import extraction."""

    def test_import_from(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        path_import = next((i for i in mod.imports if i.module == "pathlib"), None)
        assert path_import is not None
        assert "Path" in path_import.names

    def test_future_import(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        # Find any import containing 'annotations'
        future = next(
            (
                i
                for i in mod.imports
                if "annotations" in i.names or (i.module and "__future__" in i.module)
            ),
            None,
        )
        assert future is not None

    def test_relative_import(self):
        mod = extract_module_info(SAMPLE_PKG / "utils.py")
        rel_imports = [i for i in mod.imports if i.is_relative]
        assert len(rel_imports) >= 1


# ─── extract_module_info — variables & __all__ ──────────────────────────────


class TestExtractVariablesAndAll:
    """Tests for variable and __all__ extraction."""

    def test_all_exports(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        assert mod.all_exports is not None
        assert "greet" in mod.all_exports
        assert "Calculator" in mod.all_exports

    def test_variables(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        var_names = [v.name for v in mod.variables]
        assert "MAX_RETRIES" in var_names or "DEFAULT_NAME" in var_names

    def test_module_docstring(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        assert mod.docstring is not None
        assert "sample" in mod.docstring.lower()

    def test_public_functions_filtered_by_all(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        public = mod.public_functions
        public_names = [f.name for f in public]
        assert "greet" in public_names
        # _internal_helper and fetch_data should NOT be in public
        assert "_internal_helper" not in public_names

    def test_public_classes_filtered_by_all(self):
        mod = extract_module_info(SAMPLE_PKG / "__init__.py")
        public = mod.public_classes
        public_names = [c.name for c in public]
        assert "Calculator" in public_names
        assert "_InternalClass" not in public_names


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_file(self):
        mod = extract_module_info(FIXTURES / "empty.py")
        assert mod.functions == []
        assert mod.classes == []
        assert mod.docstring is None

    def test_broken_syntax(self):
        """Parser should still extract what it can from broken files."""
        mod = extract_module_info(FIXTURES / "broken.py")
        # Should not crash — tree-sitter handles errors gracefully
        assert mod.path.name == "broken.py"

    def test_nested_subpackage(self):
        mod = extract_module_info(SAMPLE_PKG / "sub" / "__init__.py")
        names = [f.name for f in mod.functions]
        assert "sub_function" in names
