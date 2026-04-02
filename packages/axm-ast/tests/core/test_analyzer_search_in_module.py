from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import (
    _find_module_by_identity,
    _find_module_by_name,
    _search_in_module,
)
from axm_ast.models import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)


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


class TestSearchInModule:
    """Unit tests for _search_in_module helper."""

    def test_match_function(
        self, sample_module: ModuleInfo, sample_func: FunctionInfo
    ) -> None:
        assert _search_in_module(sample_module, lambda s: s is sample_func) is True

    def test_match_class(
        self, sample_module: ModuleInfo, sample_class: ClassInfo
    ) -> None:
        assert _search_in_module(sample_module, lambda s: s is sample_class) is True

    def test_match_variable(
        self, sample_module: ModuleInfo, sample_var: VariableInfo
    ) -> None:
        assert _search_in_module(sample_module, lambda s: s is sample_var) is True

    def test_no_match(self, sample_module: ModuleInfo) -> None:
        assert (
            _search_in_module(sample_module, lambda s: s.name == "nonexistent") is False
        )

    def test_match_by_name(self, sample_module: ModuleInfo) -> None:
        assert _search_in_module(sample_module, lambda s: s.name == "my_func") is True


class TestFindModuleByIdentity:
    """Regression tests for _find_module_by_identity."""

    def test_finds_module_for_function(
        self,
        sample_package: PackageInfo,
        sample_func: FunctionInfo,
        sample_module: ModuleInfo,
    ) -> None:
        result = _find_module_by_identity(sample_package, sample_func)
        assert result is sample_module

    def test_finds_module_for_class(
        self,
        sample_package: PackageInfo,
        sample_class: ClassInfo,
        sample_module: ModuleInfo,
    ) -> None:
        result = _find_module_by_identity(sample_package, sample_class)
        assert result is sample_module

    def test_returns_none_for_unknown(self, sample_package: PackageInfo) -> None:
        other = FunctionInfo(name="other", line_start=1, line_end=2, decorators=[])
        assert _find_module_by_identity(sample_package, other) is None


class TestFindModuleByName:
    """Regression tests for _find_module_by_name."""

    def test_finds_by_function_name(
        self, sample_package: PackageInfo, sample_module: ModuleInfo
    ) -> None:
        result = _find_module_by_name(sample_package, "my_func")
        assert result is sample_module

    def test_finds_by_class_name(
        self, sample_package: PackageInfo, sample_module: ModuleInfo
    ) -> None:
        result = _find_module_by_name(sample_package, "MyClass")
        assert result is sample_module

    def test_finds_by_variable_name(
        self, sample_package: PackageInfo, sample_module: ModuleInfo
    ) -> None:
        result = _find_module_by_name(sample_package, "MY_VAR")
        assert result is sample_module

    def test_returns_none_for_unknown_name(self, sample_package: PackageInfo) -> None:
        assert _find_module_by_name(sample_package, "nonexistent") is None
