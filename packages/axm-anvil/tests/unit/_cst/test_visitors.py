from __future__ import annotations

import libcst as cst

from axm_anvil._cst.visitors import (
    ReferenceCollector,
    StringForwardRefScanner,
    dotted_name,
)


def test_reference_collector_names() -> None:
    expr = cst.parse_expression("x + y")
    collector = ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"x", "y"}


def test_reference_collector_attribute_chain() -> None:
    expr = cst.parse_expression("foo.bar.baz()")
    collector = ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"foo"}


def test_reference_collector_mixed() -> None:
    expr = cst.parse_expression("Path(x) / MODULE.attr")
    collector = ReferenceCollector()
    expr.visit(collector)
    assert collector.names == {"Path", "x", "MODULE"}


def test_dotted_name_simple() -> None:
    assert dotted_name(cst.Name("foo")) == "foo"


def test_dotted_name_attribute() -> None:
    node = cst.parse_expression("mylib.core.analyzer")
    assert dotted_name(node) == "mylib.core.analyzer"


def test_dotted_name_unknown_node() -> None:
    assert dotted_name(cst.Integer("3")) == ""


def test_string_forward_ref_scanner_warns() -> None:
    """AC1,AC2: a string annotation naming a moved symbol yields a warning."""
    module = cst.parse_module('def g(x: "Foo") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert any("Foo" in w for w in scanner.warnings)


def test_string_forward_ref_scanner_no_false_positive() -> None:
    """AC4: a larger identifier merely containing the name does not match."""
    module = cst.parse_module('def g(x: "FooBar") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert scanner.warnings == []


def test_string_forward_ref_scanner_subscript_match() -> None:
    """AC4: the moved name is matched as a whole identifier inside `list[Foo]`."""
    module = cst.parse_module('def g(x: "list[Foo]") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert any("Foo" in w for w in scanner.warnings)


def test_string_forward_ref_scanner_union_match() -> None:
    """AC4: the moved name is matched inside a `Foo | None` union string."""
    module = cst.parse_module('def g(x: "Foo | None") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert any("Foo" in w for w in scanner.warnings)


def test_string_forward_ref_scanner_multiple_occurrences() -> None:
    """AC1,AC2: each distinct annotation referencing a moved name warns."""
    module = cst.parse_module('def g(x: "Foo", y: "Foo") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert len(scanner.warnings) >= 2


def test_string_forward_ref_scanner_unparseable_string_ignored() -> None:
    """AC4: a non-expression annotation string does not raise and does not warn."""
    module = cst.parse_module('def g(x: "???") -> None:\n    return None\n')
    scanner = StringForwardRefScanner({"Foo"})
    module.visit(scanner)
    assert scanner.warnings == []
