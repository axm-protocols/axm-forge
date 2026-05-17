"""Split from ``test_call_helpers.py``."""

from axm_ast.core._call_helpers import extract_call_site
from axm_ast.core.parser import parse_source
from tests.unit._helpers import _first_node_of_type


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
