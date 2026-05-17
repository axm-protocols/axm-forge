from __future__ import annotations

from axm_ast.core._call_helpers import (
    update_context,
)
from axm_ast.core.parser import parse_source
from tests.unit._helpers import _first_node_of_type


def test_update_context_tracks_function_def():
    src = b"def foo():\n    pass\n"
    tree = parse_source(src.decode())
    func_node = _first_node_of_type(tree.root_node, "function_definition")
    assert func_node is not None

    new_ctx = update_context(func_node, src, current=None)

    assert new_ctx == "foo"
