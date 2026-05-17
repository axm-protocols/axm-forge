from __future__ import annotations

from axm_ast.core._call_helpers import (
    extract_call_site,
    is_call_node,
    node_text_safe,
    update_context,
)
from axm_ast.core.parser import parse_source
from tests.unit._helpers import _first_node_of_type

# ── extract_call_site ──


def test_extract_call_site_returns_callsite_for_call_node():
    tree = parse_source("foo(1, 2)\n")
    call_node = _first_node_of_type(tree.root_node, "call")
    assert call_node is not None

    site = extract_call_site(
        call_node,
        module="m",
        source_bytes=b"foo(1, 2)\n",
        context=None,
    )

    assert site is not None
    assert site.symbol == "foo"
    assert site.line == 1


# ── is_call_node ──


def test_is_call_node_true_for_call_false_for_attribute():
    call_tree = parse_source("a()\n")
    attr_tree = parse_source("a.b\n")

    call_node = _first_node_of_type(call_tree.root_node, "call")
    attr_node = _first_node_of_type(attr_tree.root_node, "attribute")

    assert call_node is not None
    assert attr_node is not None
    assert is_call_node(call_node) is True
    assert is_call_node(attr_node) is False


# ── node_text_safe ──


def test_node_text_safe_returns_empty_for_none():
    assert node_text_safe(None, b"") == ""


# ── update_context ──


def test_update_context_tracks_function_def():
    src = b"def foo():\n    pass\n"
    tree = parse_source(src.decode())
    func_node = _first_node_of_type(tree.root_node, "function_definition")
    assert func_node is not None

    new_ctx = update_context(func_node, src, current=None)

    assert new_ctx == "foo"
