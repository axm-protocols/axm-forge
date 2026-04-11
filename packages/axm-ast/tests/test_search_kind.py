from __future__ import annotations

from types import SimpleNamespace

from axm_ast.models.nodes import ClassInfo, FunctionInfo, FunctionKind
from axm_ast.tools.search import SearchTool

_fmt = SearchTool._format_symbol


# --- Unit tests ---


def test_function_has_kind() -> None:
    sym = SimpleNamespace(name="f", signature="def f()", kind="function")
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "function"


def test_method_has_kind() -> None:
    sym = SimpleNamespace(name="m", signature="def m(self)", kind="method")
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "method"


def test_class_has_kind() -> None:
    sym = ClassInfo(name="C", line_start=1, line_end=10)
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "class"


def test_variable_still_has_kind() -> None:
    sym = SimpleNamespace(name="V", value_repr="42")
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "variable"


# --- Edge cases ---


def test_property_kind() -> None:
    sym = FunctionInfo(
        name="prop",
        kind=FunctionKind.PROPERTY,
        line_start=1,
        line_end=3,
    )
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "property"


def test_abstract_method_kind() -> None:
    sym = FunctionInfo(
        name="do_thing",
        kind=FunctionKind.ABSTRACT,
        line_start=5,
        line_end=8,
    )
    entry = _fmt(sym, "mod")
    assert entry["kind"] == "abstract"
