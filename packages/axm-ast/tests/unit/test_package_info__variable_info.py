"""Split from ``test_analyzer.py``."""

from pathlib import Path

from axm_ast.core.analyzer import search_symbols
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
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


def test_variable_has_module() -> None:
    var = VariableInfo(name="VERSION", line=1, annotation="str", value_repr='"1.0"')
    mod = _make_module("pkg.consts", variables=[var])
    pkg = PackageInfo(name="pkg", root=Path("/tmp/pkg"), modules=[mod])

    results = search_symbols(pkg, name="VERSION")
    assert len(results) == 1
    assert results[0][0] == "pkg.consts"
