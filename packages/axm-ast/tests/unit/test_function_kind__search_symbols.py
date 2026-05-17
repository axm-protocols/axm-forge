"""Split from ``test_analyzer.py``."""

from pathlib import Path

from axm_ast.core.analyzer import search_symbols
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
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
