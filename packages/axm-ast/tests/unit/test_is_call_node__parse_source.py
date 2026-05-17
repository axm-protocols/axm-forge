"""Split from ``test_call_helpers.py``."""

from axm_ast.core._call_helpers import is_call_node
from axm_ast.core.parser import parse_source
from tests.unit._helpers import _first_node_of_type


def test_is_call_node_true_for_call_false_for_attribute():
    call_tree = parse_source("a()\n")
    attr_tree = parse_source("a.b\n")

    call_node = _first_node_of_type(call_tree.root_node, "call")
    attr_node = _first_node_of_type(attr_tree.root_node, "attribute")

    assert call_node is not None
    assert attr_node is not None
    assert is_call_node(call_node) is True
    assert is_call_node(attr_node) is False
