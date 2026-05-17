"""Split from ``test_nodes.py``."""

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


def test_public_api() -> None:
    pkg = PackageInfo(
        name="test",
        root=Path("/test"),
        modules=[
            ModuleInfo(
                path=Path("/test/mod.py"),
                functions=[
                    FunctionInfo(name="pub", line_start=1, line_end=5),
                    FunctionInfo(name="_priv", line_start=6, line_end=10),
                ],
            )
        ],
    )
    api = pkg.public_api
    names = [s.name for s in api]
    assert "pub" in names
    assert "_priv" not in names


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


def test_find_by_object_identity(
    sample_package: PackageInfo, sample_func: FunctionInfo
) -> None:
    mod = find_module_for_symbol(sample_package, sample_func)
    assert mod is not None
    assert any(f.name == "my_func" for f in mod.functions)


def test_unknown_object_returns_none(sample_package: PackageInfo) -> None:
    other = FunctionInfo(name="other", line_start=1, line_end=2, decorators=[])
    assert find_module_for_symbol(sample_package, other) is None
