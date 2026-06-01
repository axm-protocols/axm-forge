from __future__ import annotations

import libcst as cst
import pytest

from axm_anvil._cst.visitors import (
    ReferenceCollector,
    StringForwardRefScanner,
    dotted_name,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        pytest.param("x + y", {"x", "y"}, id="names"),
        pytest.param("foo.bar.baz()", {"foo"}, id="attribute_chain"),
        pytest.param("Path(x) / MODULE.attr", {"Path", "x", "MODULE"}, id="mixed"),
    ],
)
def test_reference_collector(expression: str, expected: set[str]) -> None:
    expr = cst.parse_expression(expression)
    collector = ReferenceCollector()
    expr.visit(collector)
    assert collector.names == expected


def test_dotted_name_simple() -> None:
    assert dotted_name(cst.Name("foo")) == "foo"


def test_dotted_name_attribute() -> None:
    node = cst.parse_expression("mylib.core.analyzer")
    assert dotted_name(node) == "mylib.core.analyzer"


def test_dotted_name_unknown_node() -> None:
    assert dotted_name(cst.Integer("3")) == ""


@pytest.mark.parametrize(
    "source",
    [
        pytest.param('def g(x: "Foo") -> None:\n    return None\n', id="warns"),
        pytest.param(
            'def g(x: "list[Foo]") -> None:\n    return None\n', id="subscript_match"
        ),
        pytest.param(
            'def g(x: "Foo | None") -> None:\n    return None\n', id="union_match"
        ),
    ],
)
def test_string_forward_ref_scanner_warns(source: str) -> None:
    """AC1,AC2,AC4: a string annotation naming a moved symbol yields a warning."""
    module = cst.parse_module(source)
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert any("Foo" in w for w in scanner.warnings)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            'def g(x: "FooBar") -> None:\n    return None\n', id="no_false_positive"
        ),
        pytest.param(
            'def g(x: "???") -> None:\n    return None\n',
            id="unparseable_string_ignored",
        ),
    ],
)
def test_string_forward_ref_scanner_no_warning(source: str) -> None:
    """AC4: a non-matching or unparseable annotation string does not warn."""
    module = cst.parse_module(source)
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert scanner.warnings == []


def test_string_forward_ref_scanner_multiple_occurrences() -> None:
    """AC1,AC2: each distinct annotation referencing a moved name warns."""
    module = cst.parse_module('def g(x: "Foo", y: "Foo") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert len(scanner.warnings) >= 2
