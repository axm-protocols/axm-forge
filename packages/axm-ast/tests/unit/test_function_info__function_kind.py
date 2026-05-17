"""Split from ``test_nodes.py``."""

from axm_ast.models.nodes import ClassInfo, FunctionInfo, FunctionKind


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
