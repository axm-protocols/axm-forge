"""Unit tests for axm_ast.core.analyzer — in-memory fixtures, no filesystem.

Covers: find_module_for_symbol, search_symbols (kind dispatch, return-type
filtering, module-name propagation, edge cases), module_dotted_name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    find_module_for_symbol,
    module_dotted_name,
    search_symbols,
)
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
    SymbolKind,
    VariableInfo,
)

# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def sample_func() -> FunctionInfo:
    return FunctionInfo(name="my_func", line_start=1, line_end=5, decorators=[])


@pytest.fixture()
def sample_class() -> ClassInfo:
    return ClassInfo(
        name="MyClass", line_start=10, line_end=20, bases=[], methods=[], decorators=[]
    )


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


@pytest.fixture()
def rich_pkg() -> PackageInfo:
    """Package with functions, classes (with methods), and variables across modules."""
    mod_vars = ModuleInfo(
        path=Path("vars.py"),
        variables=[
            VariableInfo(name="MAX_RETRIES", annotation="int", value_repr="3", line=1),
            VariableInfo(name="TIMEOUT", annotation="float", value_repr="30.0", line=2),
            VariableInfo(name="_PRIVATE", annotation=None, value_repr="True", line=3),
        ],
    )
    mod_classes = ModuleInfo(
        path=Path("models.py"),
        classes=[
            ClassInfo(
                name="User",
                bases=["BaseModel"],
                line_start=1,
                line_end=10,
                methods=[
                    FunctionInfo(
                        name="validate",
                        kind=FunctionKind.METHOD,
                        return_type="bool",
                        line_start=5,
                        line_end=8,
                    ),
                ],
            ),
            ClassInfo(name="Admin", bases=["User"], line_start=12, line_end=20),
        ],
    )
    mod_mixed = ModuleInfo(
        path=Path("mixed.py"),
        functions=[
            FunctionInfo(
                name="greet",
                kind=FunctionKind.FUNCTION,
                return_type="str",
                line_start=1,
                line_end=3,
            ),
            FunctionInfo(
                name="compute",
                kind=FunctionKind.FUNCTION,
                return_type="int",
                line_start=5,
                line_end=7,
            ),
        ],
        classes=[
            ClassInfo(
                name="Parser",
                bases=[],
                line_start=10,
                line_end=30,
                methods=[
                    FunctionInfo(
                        name="parse",
                        kind=FunctionKind.METHOD,
                        return_type="str",
                        line_start=12,
                        line_end=15,
                    ),
                    FunctionInfo(
                        name="is_valid",
                        kind=FunctionKind.PROPERTY,
                        return_type="bool",
                        line_start=17,
                        line_end=20,
                    ),
                ],
            ),
        ],
        variables=[
            VariableInfo(name="VERSION", annotation="str", value_repr='"1.0"', line=35),
        ],
    )
    return PackageInfo(
        name="demo",
        root=Path("src/demo"),
        modules=[mod_vars, mod_classes, mod_mixed],
    )


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


# ────────────────────────────────────────────────────────────────────────
# find_module_for_symbol
# ────────────────────────────────────────────────────────────────────────


class TestFindModuleForSymbol:
    """find_module_for_symbol with in-memory objects."""

    def test_find_function_by_name(self, sample_package: PackageInfo) -> None:
        mod = find_module_for_symbol(sample_package, "my_func")
        assert mod is not None
        assert any(f.name == "my_func" for f in mod.functions)

    def test_find_class_by_name(self, sample_package: PackageInfo) -> None:
        mod = find_module_for_symbol(sample_package, "MyClass")
        assert mod is not None
        assert any(c.name == "MyClass" for c in mod.classes)

    def test_find_variable_by_name(self, sample_package: PackageInfo) -> None:
        mod = find_module_for_symbol(sample_package, "MY_VAR")
        assert mod is not None
        assert any(v.name == "MY_VAR" for v in mod.variables)

    def test_find_by_object_identity(
        self, sample_package: PackageInfo, sample_func: FunctionInfo
    ) -> None:
        mod = find_module_for_symbol(sample_package, sample_func)
        assert mod is not None
        assert any(f.name == "my_func" for f in mod.functions)

    def test_find_class_by_object(
        self, sample_package: PackageInfo, sample_class: ClassInfo
    ) -> None:
        mod = find_module_for_symbol(sample_package, sample_class)
        assert mod is not None
        assert any(c.name == "MyClass" for c in mod.classes)

    def test_unknown_name_returns_none(self, sample_package: PackageInfo) -> None:
        assert find_module_for_symbol(sample_package, "nonexistent") is None

    def test_unknown_object_returns_none(self, sample_package: PackageInfo) -> None:
        other = FunctionInfo(name="other", line_start=1, line_end=2, decorators=[])
        assert find_module_for_symbol(sample_package, other) is None


# ────────────────────────────────────────────────────────────────────────
# search_symbols — kind dispatch
# ────────────────────────────────────────────────────────────────────────


class TestSearchVariableKind:
    def test_returns_only_variables(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.VARIABLE)
        names = [sym.name for _, sym in results]
        assert "VERSION" in names
        assert "MAX_RETRIES" in names
        assert "greet" not in names
        assert "User" not in names

    def test_variable_kind_with_name_filter(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.VARIABLE, name="TIMEOUT")
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


class TestSearchClassKind:
    def test_returns_only_classes(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.CLASS)
        names = [sym.name for _, sym in results]
        assert "User" in names
        assert "Admin" in names
        assert "greet" not in names
        assert "VERSION" not in names

    def test_class_kind_with_name_filter(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.CLASS, name="Admin")
        assert len(results) == 1
        assert results[0][1].name == "Admin"


class TestSearchFunctionKind:
    def test_returns_top_level_functions(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.FUNCTION)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "compute" in names
        assert "Parser" not in names
        assert "VERSION" not in names

    def test_method_kind_returns_methods(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.METHOD)
        names = [sym.name for _, sym in results]
        assert "parse" in names
        assert "greet" not in names

    def test_property_kind_returns_properties(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.PROPERTY)
        names = [sym.name for _, sym in results]
        assert "is_valid" in names
        assert "parse" not in names


# ────────────────────────────────────────────────────────────────────────
# search_symbols — name, return type, inheritance filters
# ────────────────────────────────────────────────────────────────────────


class TestSearchByName:
    def test_search_by_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, name="greet")
        assert len(results) >= 1
        assert any(sym.name == "greet" for _, sym in results)

    def test_substring_match(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, name="RETRI")
        assert any(sym.name == "MAX_RETRIES" for _, sym in results)


class TestSearchByReturnType:
    def test_filter_by_return_type(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, returns="str")
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "User" not in names

    def test_return_type_includes_methods(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, returns="bool")
        names = [sym.name for _, sym in results]
        assert "validate" in names or "is_valid" in names


class TestSearchByKindAndName:
    def test_function_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.FUNCTION, name="greet")
        assert len(results) == 1
        assert results[0][1].name == "greet"

    def test_class_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.CLASS, name="User")
        assert len(results) == 1
        assert results[0][1].name == "User"

    def test_variable_kind_with_name(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.VARIABLE, name="TIMEOUT")
        assert len(results) == 1
        assert results[0][1].name == "TIMEOUT"


class TestSearchInherits:
    def test_inherits_base_model(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="BaseModel")
        names = [sym.name for _, sym in results]
        assert "User" in names

    def test_inherits_user(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="User")
        names = [sym.name for _, sym in results]
        assert "Admin" in names

    def test_inherits_nonexistent(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, inherits="NonExistent")
        assert results == []


# ────────────────────────────────────────────────────────────────────────
# search_symbols — return-type filtering
# ────────────────────────────────────────────────────────────────────────


class TestSearchReturnsFilter:
    """Verifies return-type filtering behavior."""

    def test_returns_excludes_variables(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, returns="str")
        names = [sym.name for _, sym in results]
        assert "_PRIVATE" not in names
        assert "greet" in names

    def test_returns_excludes_name_matched_classes(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, name="User", returns="int")
        names = [sym.name for _, sym in results]
        assert "User" not in names

    def test_no_returns_still_includes_variables(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg)
        names = [sym.name for _, sym in results]
        assert "_PRIVATE" in names

    def test_name_match_no_returns_still_returns_class(
        self, rich_pkg: PackageInfo
    ) -> None:
        results = search_symbols(rich_pkg, name="User")
        names = [sym.name for _, sym in results]
        assert "User" in names

    def test_returns_name_matching_class_only_matching_methods(self) -> None:
        mod = ModuleInfo(
            path=Path("edge.py"),
            classes=[
                ClassInfo(
                    name="User",
                    bases=[],
                    line_start=1,
                    line_end=20,
                    methods=[
                        FunctionInfo(
                            name="UserSerializer",
                            kind=FunctionKind.METHOD,
                            return_type="str",
                            line_start=3,
                            line_end=5,
                        ),
                        FunctionInfo(
                            name="get_id",
                            kind=FunctionKind.METHOD,
                            return_type="int",
                            line_start=7,
                            line_end=9,
                        ),
                    ],
                ),
            ],
        )
        pkg = PackageInfo(name="edge", root=Path("edge"), modules=[mod])
        results = search_symbols(pkg, name="User", returns="str")
        names = [sym.name for _, sym in results]
        assert "User" not in names
        assert "UserSerializer" in names
        assert "get_id" not in names

    def test_returns_on_variables_only_module(self) -> None:
        mod = ModuleInfo(
            path=Path("vars_only.py"),
            variables=[VariableInfo(name="MAX_SIZE", line=1)],
        )
        pkg = PackageInfo(name="vars", root=Path("vars"), modules=[mod])
        results = search_symbols(pkg, returns="int")
        assert results == []


# ────────────────────────────────────────────────────────────────────────
# search_symbols — module-name propagation (AXM-1313)
# ────────────────────────────────────────────────────────────────────────


class TestSearchModuleField:
    def test_results_carry_module(self) -> None:
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

    def test_variable_has_module(self) -> None:
        var = VariableInfo(name="VERSION", line=1, annotation="str", value_repr='"1.0"')
        mod = _make_module("pkg.consts", variables=[var])
        pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

        results = search_symbols(pkg, name="VERSION")
        assert len(results) == 1
        assert results[0][0] == "pkg.consts"

    def test_init_module_path(self) -> None:
        fn = FunctionInfo(
            name="greet",
            kind=FunctionKind.FUNCTION,
            line_start=5,
            line_end=7,
            decorators=[],
        )
        mod = _make_module("pkg.__init__", functions=[fn])
        pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

        results = search_symbols(pkg, name="greet")
        assert len(results) == 1
        assert results[0][0] == "pkg.__init__"

    def test_nested_subpackage_module(self) -> None:
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


# ────────────────────────────────────────────────────────────────────────
# search_symbols — edge cases
# ────────────────────────────────────────────────────────────────────────


class TestSearchEdgeCases:
    def test_variable_kind_with_returns_empty(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.VARIABLE, returns="str")
        assert results == []

    def test_class_kind_with_returns_empty(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg, kind=SymbolKind.CLASS, returns="int")
        assert results == []

    def test_no_filters_returns_all(self, rich_pkg: PackageInfo) -> None:
        results = search_symbols(rich_pkg)
        names = [sym.name for _, sym in results]
        assert "greet" in names
        assert "compute" in names
        assert "parse" in names
        assert "VERSION" in names

    def test_empty_package(self) -> None:
        pkg = PackageInfo(name="empty", root=Path("empty"), modules=[])
        results = search_symbols(pkg)
        assert results == []


# ────────────────────────────────────────────────────────────────────────
# module_dotted_name
# ────────────────────────────────────────────────────────────────────────


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
