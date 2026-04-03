from __future__ import annotations

from axm_ast.hooks.source_body import _dedup_symbols

# --- Unit tests ---


def test_dedup_class_and_method():
    assert _dedup_symbols(["Foo", "Foo.validate"]) == ["Foo"]


def test_dedup_class_and_multiple_methods():
    assert _dedup_symbols(["Foo", "Foo.validate", "Foo._helper"]) == ["Foo"]


def test_dedup_method_only():
    """No class to subsume — method kept as-is."""
    assert _dedup_symbols(["Foo.validate"]) == ["Foo.validate"]


def test_dedup_unrelated():
    assert _dedup_symbols(["Foo", "Bar.validate"]) == ["Foo", "Bar.validate"]


def test_dedup_bare_functions():
    """No dotted names — nothing to dedup."""
    assert _dedup_symbols(["func_a", "func_b"]) == ["func_a", "func_b"]


def test_dedup_preserves_order():
    """Order follows first appearance; subsumed entries removed in place."""
    assert _dedup_symbols(["Foo.validate", "Foo", "Bar"]) == ["Foo", "Bar"]


# --- Edge cases ---


def test_dedup_empty_list():
    assert _dedup_symbols([]) == []


def test_dedup_single_class():
    assert _dedup_symbols(["Foo"]) == ["Foo"]


def test_dedup_single_method():
    assert _dedup_symbols(["Foo.bar"]) == ["Foo.bar"]


def test_dedup_nested_dotted():
    """Foo.Inner.method is subsumed by Foo (prefix match on first segment)."""
    assert _dedup_symbols(["Foo", "Foo.Inner.method"]) == ["Foo"]
