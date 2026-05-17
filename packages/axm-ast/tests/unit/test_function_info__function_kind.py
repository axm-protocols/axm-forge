"""Split from ``test_nodes.py``."""

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


def test_basic_function():
    fn = FunctionInfo(name="foo", line_start=1, line_end=3)
    assert fn.name == "foo"
    assert fn.kind == FunctionKind.FUNCTION
    assert fn.is_public is True
    assert fn.is_async is False


def test_all_kinds():
    for kind in FunctionKind:
        fn = FunctionInfo(name="x", kind=kind, line_start=1, line_end=1)
        assert fn.kind == kind


def test_class_with_methods():
    method = FunctionInfo(
        name="parse",
        kind=FunctionKind.METHOD,
        line_start=3,
        line_end=10,
    )
    cls = ClassInfo(name="Parser", methods=[method], line_start=1, line_end=10)
    assert len(cls.methods) == 1
    assert cls.methods[0].kind == FunctionKind.METHOD


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


def test_returns_name_matching_class_only_matching_methods() -> None:
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


def test_init_module_path() -> None:
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
