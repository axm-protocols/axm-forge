"""Split from ``test_analyzer.py``."""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import find_module_for_symbol, search_symbols
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
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


def test_find_class_by_object(
    sample_package: PackageInfo, sample_class: ClassInfo
) -> None:
    mod = find_module_for_symbol(sample_package, sample_class)
    assert mod is not None
    assert any(c.name == "MyClass" for c in mod.classes)


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
