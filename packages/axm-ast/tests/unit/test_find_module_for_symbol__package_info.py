"""Split from ``test_analyzer.py``."""

from pathlib import Path

import pytest

from axm_ast.core.analyzer import find_module_for_symbol
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
