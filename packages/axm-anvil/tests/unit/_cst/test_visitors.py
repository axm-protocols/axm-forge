from __future__ import annotations

import libcst as cst

from axm_anvil._cst.visitors import _dotted_name, _ReferenceCollector


def test_reference_collector_names() -> None:
    expr = cst.parse_expression("x + y")
    collector = _ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"x", "y"}


def test_reference_collector_attribute_chain() -> None:
    expr = cst.parse_expression("foo.bar.baz()")
    collector = _ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"foo"}


def test_reference_collector_mixed() -> None:
    expr = cst.parse_expression("Path(x) / MODULE.attr")
    collector = _ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"Path", "x", "MODULE"}


def test_dotted_name_simple() -> None:
    assert _dotted_name(cst.Name("foo")) == "foo"


def test_dotted_name_attribute() -> None:
    node = cst.parse_expression("mylib.core.analyzer")
    assert _dotted_name(node) == "mylib.core.analyzer"


def test_dotted_name_unknown_node() -> None:
    assert _dotted_name(cst.Integer("3")) == ""
