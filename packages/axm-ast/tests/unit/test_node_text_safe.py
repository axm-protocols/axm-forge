"""Split from ``test_call_helpers.py``."""

from axm_ast.core._call_helpers import node_text_safe


def test_node_text_safe_returns_empty_for_none():
    assert node_text_safe(None, b"") == ""
