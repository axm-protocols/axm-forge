"""Unit tests for axm_ast.core.analyzer.

Covers: analyze_package, build_import_graph, module_dotted_name,
search_symbols (name, return-type, inheritance, kind dispatch, module
propagation, edge cases), find_module_for_symbol.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import FunctionKind as _PublicFunctionKind
from axm_ast import ModuleInfo as _PublicModuleInfo
from axm_ast import PackageInfo as _PublicPackageInfo
from axm_ast import analyze_package as _public_analyze_package
from axm_ast.core.analyzer import (
    analyze_package,
    build_import_graph,
    find_module_for_symbol,
    module_dotted_name,
    search_symbols,
)
from axm_ast.core.dead_code import find_dead_code
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
    SymbolKind,
    VariableInfo,
)

_AXM_AST_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SAMPLE_PKG = FIXTURES / "sample_pkg"


# ── Helpers & local fixtures ──


def _make_module(
    name: str,
    *,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    variables: list[VariableInfo] | None = None,
) -> ModuleInfo:
    return ModuleInfo(
        name=name,
        path=Path(f"{name.replace('.', '/')}.py"),
        imports=[],
        functions=functions or [],
        classes=classes or [],
        variables=variables or [],
    )


def _module_by_name(pkg: PackageInfo, name: str) -> ModuleInfo:
    """Return the module whose path ends with *name*."""
    return next(m for m in pkg.modules if m.path.name == name)


@pytest.fixture()
def sample_var() -> VariableInfo:
    return VariableInfo(name="MY_VAR", line=25)


@pytest.fixture()
def sample_module(
    sample_func: FunctionInfo, sample_class: ClassInfo, sample_var: VariableInfo
) -> ModuleInfo:
    return ModuleInfo(
        path=Path("mod.py"),
        functions=[sample_func],
        classes=[sample_class],
        variables=[sample_var],
    )


@pytest.fixture()
def sample_package(sample_module: ModuleInfo) -> PackageInfo:
    return PackageInfo(name="pkg", root=Path("pkg"), modules=[sample_module])


# ── analyze_package — dead-code regression ──


def test_describe_data_not_reported_dead() -> None:
    """After the patch, axm-ast's _DescribeData is no longer flagged."""
    pkg = analyze_package(_AXM_AST_ROOT)
    dead = find_dead_code(pkg)
    assert "_DescribeData" not in {d.name for d in dead}


# ── module_dotted_name ──


class TestModuleDottedName:
    def test_src_layout(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/core.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg.core"

    def test_flat_layout(self) -> None:
        result = module_dotted_name(Path("/tmp/pkg/mypkg/core.py"), Path("/tmp/pkg"))
        assert result == "mypkg.core"

    def test_init_file(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/__init__.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg"

    def test_package_named_src(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/src/__init__.py"), Path("/tmp/pkg")
        )
        assert result == "src"

    def test_nested_src_dirs(self) -> None:
        result = module_dotted_name(
            Path("/tmp/pkg/src/mypkg/src/inner.py"), Path("/tmp/pkg")
        )
        assert result == "mypkg.src.inner"


# ── search_symbols — name, return type, inheritance filters ──


def test_returns_on_variables_only_module() -> None:
    mod = ModuleInfo(
        path=Path("vars_only.py"),
        variables=[VariableInfo(name="MAX_SIZE", line=1)],
    )
    pkg = PackageInfo(name="vars", root=Path("vars"), modules=[mod])
    results = search_symbols(pkg, returns="int")
    assert results == []


class TestSearchByName:
    def test_search_by_name(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, name="greet")
        assert len(results) >= 1
        assert any(sym.name == "greet" for _, sym in results)

    def test_substring_match(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, name="RETRI")
        assert any(sym.name == "MAX_RETRIES" for _, sym in results)


class TestSearchByReturnType:
    def test_filter_by_return_type(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "User" not in names

    def test_return_type_includes_methods(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, returns="bool")
        names = [sym.name for _, sym in results]
        assert "validate" in names or "is_valid" in names


class TestSearchInherits:
    def test_inherits_base_model(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="BaseModel")
        names = [sym.name for _, sym in results]
        assert "User" in names

    def test_inherits_user(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="User")
        names = [sym.name for _, sym in results]
        assert "Admin" in names

    def test_inherits_nonexistent(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, inherits="NonExistent")
        assert results == []


def test_returns_excludes_variables(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(rich_pkg__from_analyzer, returns="str")
    names = [sym.name for _, sym in results]
    assert "_PRIVATE" not in names
    assert "greet" in names


def test_returns_excludes_name_matched_classes(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer, name="User", returns="int")
    names = [sym.name for _, sym in results]
    assert "User" not in names


def test_no_returns_still_includes_variables(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer)
    names = [sym.name for _, sym in results]
    assert "_PRIVATE" in names


def test_name_match_no_returns_still_returns_class(
    rich_pkg__from_analyzer: PackageInfo,
) -> None:
    results = search_symbols(rich_pkg__from_analyzer, name="User")
    names = [sym.name for _, sym in results]
    assert "User" in names


def test_no_filters_returns_all(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(rich_pkg__from_analyzer)
    names = [sym.name for _, sym in results]
    assert "greet" in names
    assert "compute" in names
    assert "parse" in names
    assert "VERSION" in names


def test_empty_package() -> None:
    pkg = PackageInfo(name="empty", root=Path("empty"), modules=[])
    results = search_symbols(pkg)
    assert results == []


# ── search_symbols — kind dispatch ──


def test_variable_kind_with_returns_empty(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(
        rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, returns="str"
    )
    assert results == []


def test_class_kind_with_returns_empty(rich_pkg__from_analyzer: PackageInfo) -> None:
    results = search_symbols(
        rich_pkg__from_analyzer, kind=SymbolKind.CLASS, returns="int"
    )
    assert results == []


class TestSearchVariableKind:
    def test_returns_only_variables(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE)
        names = [sym.name for _, sym in results]
        assert "VERSION" in names
        assert "MAX_RETRIES" in names
        assert "greet" not in names
        assert "User" not in names

    def test_variable_kind_with_name_filter(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, name="TIMEOUT"
        )
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


class TestSearchClassKind:
    def test_returns_only_classes(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.CLASS)
        names = [sym.name for _, sym in results]
        assert "User" in names
        assert "Admin" in names
        assert "greet" not in names
        assert "VERSION" not in names

    def test_class_kind_with_name_filter(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.CLASS, name="Admin"
        )
        assert len(results) == 1
        assert results[0][1].name == "Admin"


class TestSearchFunctionKind:
    def test_returns_top_level_functions(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.FUNCTION)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "compute" in names
        assert "Parser" not in names
        assert "VERSION" not in names

    def test_method_kind_returns_methods(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.METHOD)
        names = [sym.name for _, sym in results]
        assert "parse" in names
        assert "greet" not in names

    def test_property_kind_returns_properties(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg__from_analyzer, kind=SymbolKind.PROPERTY)
        names = [sym.name for _, sym in results]
        assert "is_valid" in names
        assert "parse" not in names


class TestSearchByKindAndName:
    def test_function_kind_with_name(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.FUNCTION, name="greet"
        )
        assert len(results) == 1
        assert results[0][1].name == "greet"

    def test_class_kind_with_name(self, rich_pkg__from_analyzer: PackageInfo) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.CLASS, name="User"
        )
        assert len(results) == 1
        assert results[0][1].name == "User"

    def test_variable_kind_with_name(
        self, rich_pkg__from_analyzer: PackageInfo
    ) -> None:
        results = search_symbols(
            rich_pkg__from_analyzer, kind=SymbolKind.VARIABLE, name="TIMEOUT"
        )
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


# ── search_symbols — module-name propagation (in-memory PackageInfo) ──


def test_results_carry_module() -> None:
    fn = FunctionInfo(
        name="greet",
        kind=FunctionKind.FUNCTION,
        return_type="str",
        line_start=5,
        line_end=7,
        decorators=[],
    )
    cls = ClassInfo(
        name="Greeter",
        bases=["object"],
        line_start=10,
        line_end=20,
        decorators=[],
        methods=[],
    )
    mod_a = _make_module("pkg.alpha", functions=[fn])
    mod_b = _make_module("pkg.beta", classes=[cls])
    pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod_a, mod_b])

    fn_results = search_symbols(pkg, name="greet")
    assert len(fn_results) == 1
    assert fn_results[0][0] == "pkg.alpha"

    cls_results = search_symbols(pkg, name="Greeter")
    assert len(cls_results) == 1
    assert cls_results[0][0] == "pkg.beta"


def test_variable_has_module() -> None:
    var = VariableInfo(name="VERSION", line=1, annotation="str", value_repr='"1.0"')
    mod = _make_module("pkg.consts", variables=[var])
    pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

    results = search_symbols(pkg, name="VERSION")
    assert len(results) == 1
    assert results[0][0] == "pkg.consts"


def test_nested_subpackage_module() -> None:
    cls = ClassInfo(
        name="Greeter",
        bases=["object"],
        line_start=10,
        line_end=20,
        decorators=[],
        methods=[],
    )
    mod = _make_module("pkg.sub.mod", classes=[cls])
    pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

    results = search_symbols(pkg, name="Greeter")
    assert len(results) == 1
    assert results[0][0] == "pkg.sub.mod"


# ── find_module_for_symbol — in-memory fixtures ──


def test_find_function_by_name(sample_package: PackageInfo) -> None:
    mod = find_module_for_symbol(sample_package, "my_func")
    assert mod is not None
    assert any(f.name == "my_func" for f in mod.functions)


def test_find_class_by_name(sample_package: PackageInfo) -> None:
    mod = find_module_for_symbol(sample_package, "MyClass")
    assert mod is not None
    assert any(c.name == "MyClass" for c in mod.classes)


def test_find_variable_by_name(sample_package: PackageInfo) -> None:
    mod = find_module_for_symbol(sample_package, "MY_VAR")
    assert mod is not None
    assert any(v.name == "MY_VAR" for v in mod.variables)


def test_unknown_name_returns_none(sample_package: PackageInfo) -> None:
    assert find_module_for_symbol(sample_package, "nonexistent") is None


def test_find_class_by_object(
    sample_package: PackageInfo, sample_class: ClassInfo
) -> None:
    mod = find_module_for_symbol(sample_package, sample_class)
    assert mod is not None
    assert any(c.name == "MyClass" for c in mod.classes)


# ── build_import_graph — real fixture package ──


@pytest.mark.integration
class TestBuildImportGraph:
    """Tests for internal import graph construction."""

    def test_graph_contains_modules(self):
        pkg = analyze_package(SAMPLE_PKG)
        graph = build_import_graph(pkg)
        assert len(graph) > 0, "Graph should contain at least one module"


# ── search_symbols — integration against real fixture package ──


@pytest.mark.integration
class TestSearchSymbolsIntegration:
    """Tests for semantic search across a real package."""

    def test_search_by_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="greet")
        assert len(results) >= 1
        assert results[0][1].name == "greet"

    def test_search_by_return_type(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names

    def test_search_by_kind(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.PROPERTY)
        assert len(results) >= 1
        assert all(
            isinstance(sym, FunctionInfo) and sym.kind == FunctionKind.PROPERTY
            for _, sym in results
        )

    def test_search_by_kind_class(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.CLASS)
        assert len(results) >= 1
        assert all(isinstance(sym, ClassInfo) for _, sym in results)

    def test_search_by_kind_function(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.FUNCTION)
        assert len(results) >= 1
        assert all(
            isinstance(sym, FunctionInfo) and sym.kind == FunctionKind.FUNCTION
            for _, sym in results
        )
        names = [sym.name for _, sym in results]
        assert "Calculator" not in names

    def test_search_no_results(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="nonexistent_xyz")
        assert results == []

    def test_search_by_base_class(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, inherits="BaseModel")
        assert results == []

    def test_search_variable_by_name(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        assert len(results) >= 1
        match = [sym for _, sym in results if sym.name == "MAX_RETRIES"]
        assert len(match) == 1
        assert isinstance(match[0], VariableInfo)
        assert match[0].line > 0

    def test_search_variable_kind_filter(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, kind=SymbolKind.VARIABLE)
        assert len(results) >= 1
        assert all(isinstance(sym, VariableInfo) for _, sym in results)
        names = [sym.name for _, sym in results]
        assert "MAX_RETRIES" in names
        assert "DEFAULT_NAME" in names
        assert "greet" not in names
        assert "Calculator" not in names

    def test_search_kind_none_includes_variables(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "MAX_RETRIES" in names

    def test_search_annotated_variable(self) -> None:
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="MAX_RETRIES")
        match = [sym for _, sym in results if sym.name == "MAX_RETRIES"]
        assert len(match) == 1
        var = match[0]
        assert isinstance(var, VariableInfo)
        assert var.annotation == "int"


# ── find_module_for_symbol — integration against real fixture package ──


@pytest.mark.integration
class TestFindModuleForSymbolIntegration:
    """Tests for find_module_for_symbol()."""

    def test_find_by_function_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "greet")
        assert mod is not None
        assert any(f.name == "greet" for f in mod.functions)

    def test_find_by_class_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "Calculator")
        assert mod is not None
        assert any(c.name == "Calculator" for c in mod.classes)

    def test_find_by_variable_name(self):
        pkg = analyze_package(SAMPLE_PKG)
        mod = find_module_for_symbol(pkg, "MAX_RETRIES")
        assert mod is not None
        assert any(v.name == "MAX_RETRIES" for v in mod.variables)

    def test_find_by_object_identity(self):
        pkg = analyze_package(SAMPLE_PKG)
        results = search_symbols(pkg, name="greet")
        assert len(results) >= 1
        _, func = results[0]
        mod = find_module_for_symbol(pkg, func)
        assert mod is not None
        assert any(f.name == "greet" for f in mod.functions)

    def test_find_unknown_returns_none(self):
        pkg = analyze_package(SAMPLE_PKG)
        assert find_module_for_symbol(pkg, "nonexistent_xyz") is None


# ── analyze_package — public API boundary (module discovery, naming, root) ──


@pytest.mark.functional
class TestAnalyzePackageUnit:
    """Tests for analyze_package() (pure, fixture-only)."""

    def test_discovers_all_modules(self):
        pkg = _public_analyze_package(SAMPLE_PKG)
        assert len(pkg.modules) >= 3

    def test_package_name(self):
        pkg = _public_analyze_package(SAMPLE_PKG)
        assert pkg.name == "sample_pkg"

    def test_package_root(self):
        pkg = _public_analyze_package(SAMPLE_PKG)
        assert pkg.root == SAMPLE_PKG.resolve()

    def test_module_names_populated(self):
        pkg = _public_analyze_package(SAMPLE_PKG)
        assert len(pkg.module_names) >= 3


# ── analyze_package — module extraction through the public API ──


@pytest.mark.functional
class TestFunctionExtraction:
    """Function extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = _public_analyze_package(SAMPLE_PKG)
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


@pytest.mark.functional
class TestClassExtraction:
    """Class extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = _public_analyze_package(SAMPLE_PKG)
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
        assert name_method.kind == _PublicFunctionKind.PROPERTY

    def test_staticmethod(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        version = next(m for m in calc.methods if m.name == "version")
        assert version.kind == _PublicFunctionKind.STATICMETHOD

    def test_classmethod(self):
        calc = next(c for c in self.init_mod.classes if c.name == "Calculator")
        from_cfg = next(m for m in calc.methods if m.name == "from_config")
        assert from_cfg.kind == _PublicFunctionKind.CLASSMETHOD


@pytest.mark.functional
class TestImportExtraction:
    """Import extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = _public_analyze_package(SAMPLE_PKG)

    def test_import_from(self):
        init_mod = _module_by_name(self.pkg, "__init__.py")
        path_import = next((i for i in init_mod.imports if i.module == "pathlib"), None)
        assert path_import is not None
        assert "Path" in path_import.names

    def test_relative_import(self):
        utils_mod = _module_by_name(self.pkg, "utils.py")
        rel_imports = [i for i in utils_mod.imports if i.is_relative]
        assert len(rel_imports) >= 1


@pytest.mark.functional
class TestVariablesAndAll:
    """Variable and __all__ extraction through the public API."""

    @pytest.fixture(autouse=True)
    def _pkg(self):
        self.pkg = _public_analyze_package(SAMPLE_PKG)
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


@pytest.mark.functional
class TestEdgeCases:
    """Edge-case extraction through the public API."""

    def test_nested_subpackage(self):
        pkg = _public_analyze_package(SAMPLE_PKG)
        sub_mod = _module_by_name(pkg, "__init__.py")
        # The sub-package __init__.py with sub_function is part of the package
        sub_mods = [m for m in pkg.modules if "sub" in str(m.path)]
        assert len(sub_mods) >= 1
        sub_mod = sub_mods[0]
        names = [f.name for f in sub_mod.functions]
        assert "sub_function" in names


# Ensure re-exported public API aliases match the internal symbols.
assert _PublicModuleInfo is ModuleInfo
assert _PublicPackageInfo is PackageInfo
