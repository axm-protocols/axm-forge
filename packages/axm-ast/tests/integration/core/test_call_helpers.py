from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from tree_sitter import Node

from axm_ast.core._call_helpers import (
    extract_call_site,
    is_call_node,
    node_text_safe,
    update_context,
)
from axm_ast.core.analyzer import analyze_package
from axm_ast.core.callers import find_callers
from axm_ast.core.flows import trace_flow
from axm_ast.core.parser import parse_source


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _first_node_of_type(root: Node, type_name: str) -> Node | None:
    for n in _walk(root):
        if n.type == type_name:
            return n
    return None


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


def test_is_call_node_true_for_call_false_for_attribute():
    call_tree = parse_source("a()\n")
    attr_tree = parse_source("a.b\n")

    call_node = _first_node_of_type(call_tree.root_node, "call")
    attr_node = _first_node_of_type(attr_tree.root_node, "attribute")

    assert call_node is not None
    assert attr_node is not None
    assert is_call_node(call_node) is True
    assert is_call_node(attr_node) is False


def test_node_text_safe_returns_empty_for_none():
    assert node_text_safe(None, b"") == ""


def test_update_context_tracks_function_def():
    src = b"def foo():\n    pass\n"
    tree = parse_source(src.decode())
    func_node = _first_node_of_type(tree.root_node, "function_definition")
    assert func_node is not None

    new_ctx = update_context(func_node, src, current=None)

    assert new_ctx == "foo"


@pytest.fixture
def tiny_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text(
        "def foo():\n    return 1\n\ndef caller():\n    return foo()\n"
    )
    return pkg


def test_find_callers_still_works_after_helper_extraction(tiny_pkg: Path) -> None:
    info = analyze_package(tiny_pkg)
    results = find_callers(info, "foo")

    assert len(results) == 1
    assert results[0].symbol == "foo"


@pytest.fixture
def chain_pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "m.py").write_text(
        "def c():\n    return 0\n\n"
        "def b():\n    return c()\n\n"
        "def a():\n    return b()\n"
    )
    return pkg


def test_trace_flow_still_works_after_helper_extraction(chain_pkg: Path) -> None:
    info = analyze_package(chain_pkg)
    steps, _truncated = trace_flow(info, "a", max_depth=5)

    names = [s.name for s in steps]
    assert "a" in names
    assert "b" in names
    assert "c" in names
    assert len(steps) >= 3
