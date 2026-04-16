"""Functional tests for module extraction through analyze_package.

All tests hit the public API boundary (analyze_package) and exercise
parser behavior end-to-end on fixture packages.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import FunctionKind, ModuleInfo, PackageInfo, analyze_package

FIXTURES = Path(__file__).parents[1] / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


def _module_by_name(pkg: PackageInfo, name: str) -> ModuleInfo:
    """Return the module whose path ends with *name*."""
    return next(m for m in pkg.modules if m.path.name == name)


# ─── Functions ──────────────────────────────────────────────────────────────


@pytest.mark.functional
class TestFunctionExtraction:
    """Function extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = analyze_package(SAMPLE_PKG)
        self.init_mod = _module_by_name(self.pkg, "__init__.py")

    def test_extracts_public_function(self):
        names = [f.name for f in self.init_mod.functions]
        assert "greet" in names

    def test_extracts_private_function(self):
        names = [f.name for f in self.init_mod.functions]
        assert "_internal_helper" in names

    def test_function_params(self):
        greet = next(f for f in self.init_mod.functions if f.name == "greet")
        assert len(greet.params) == 1
        assert greet.params[0].name == "name"
        assert greet.params[0].annotation == "str"
        assert greet.params[0].default == '"world"'

    def test_function_return_type(self):
        greet = next(f for f in self.init_mod.functions if f.name == "greet")
        assert greet.return_type == "str"

    def test_function_docstring(self):
        greet = next(f for f in self.init_mod.functions if f.name == "greet")
        assert greet.docstring is not None
        assert "greeting" in greet.docstring.lower()

    def test_async_function_return_type(self):
        fetch = next(f for f in self.init_mod.functions if f.name == "fetch_data")
        assert fetch.return_type == "dict[str, Any]"

    def test_function_line_range(self):
        greet = next(f for f in self.init_mod.functions if f.name == "greet")
        assert greet.line_start > 0
        assert greet.line_end >= greet.line_start


# ─── Classes ────────────────────────────────────────────────────────────────


@pytest.mark.functional
class TestClassExtraction:
    """Class extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = analyze_package(SAMPLE_PKG)
        self.init_mod = _module_by_name(self.pkg, "__init__.py")

    def test_extracts_public_class(self):
        names = [c.name for c in self.init_mod.classes]
        assert "Calculator" in names

    def test_extracts_private_class(self):
        names = [c.name for c in self.init_mod.classes]
        assert "_InternalClass" in names

    def test_class_docstring(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        assert calc.docstring is not None
        assert "calculator" in calc.docstring.lower()

    def test_class_methods_extracted(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        method_names = [m.name for m in calc.methods]
        assert "__init__" in method_names
        assert "add" in method_names

    def test_property_method(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        name_method = next(m for m in calc.methods if m.name == "name")
        assert name_method.kind == FunctionKind.PROPERTY

    def test_staticmethod(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        version = next(m for m in calc.methods if m.name == "version")
        assert version.kind == FunctionKind.STATICMETHOD

    def test_classmethod(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        from_cfg = next(m for m in calc.methods if m.name == "from_config")
        assert from_cfg.kind == FunctionKind.CLASSMETHOD


# ─── Imports ────────────────────────────────────────────────────────────────


@pytest.mark.functional
class TestImportExtraction:
    """Import extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = analyze_package(SAMPLE_PKG)

    def test_import_from(self):
        init_mod = _module_by_name(self.pkg, "__init__.py")
        path_import = next((i for i in init_mod.imports if i.module == "pathlib"), None)
        assert path_import is not None
        assert "Path" in path_import.names

    def test_future_import(self):
        init_mod = _module_by_name(self.pkg, "__init__.py")
        future = next(
            (i for i in init_mod.imports if "annotations" in i.names),
            None,
        )
        assert future is not None

    def test_relative_import(self):
        utils_mod = _module_by_name(self.pkg, "utils.py")
        rel_imports = [i for i in utils_mod.imports if i.is_relative]
        assert len(rel_imports) >= 1


# ─── Variables & __all__ ────────────────────────────────────────────────────


@pytest.mark.functional
class TestVariablesAndAll:
    """Variable and __all__ extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = analyze_package(SAMPLE_PKG)
        self.init_mod = _module_by_name(self.pkg, "__init__.py")

    def test_all_exports(self):
        assert self.init_mod.all_exports is not None
        assert "greet" in self.init_mod.all_exports
        assert "Calculator" in self.init_mod.all_exports

    def test_variables(self):
        var_names = [v.name for v in self.init_mod.variables]
        assert "MAX_RETRIES" in var_names
        assert "DEFAULT_NAME" in var_names

    def test_module_docstring(self):
        assert self.init_mod.docstring is not None
        assert "sample" in self.init_mod.docstring.lower()

    def test_public_functions_filtered_by_all(self):
        public_names = [f.name for f in self.init_mod.public_functions]
        assert "greet" in public_names
        assert "_internal_helper" not in public_names

    def test_public_classes_filtered_by_all(self):
        public_names = [c.name for c in self.init_mod.public_classes]
        assert "Calculator" in public_names
        assert "_InternalClass" not in public_names


# ─── Edge cases ─────────────────────────────────────────────────────────────


@pytest.mark.functional
class TestEdgeCases:
    """Edge-case extraction through the public API."""

    def test_nested_subpackage(self):
        pkg = analyze_package(SAMPLE_PKG)
        sub_mod = _module_by_name(pkg, "__init__.py")
        # The sub-package __init__.py with sub_function is part of the package
        sub_mods = [m for m in pkg.modules if "sub" in str(m.path)]
        assert len(sub_mods) >= 1
        sub_mod = sub_mods[0]
        names = [f.name for f in sub_mod.functions]
        assert "sub_function" in names
