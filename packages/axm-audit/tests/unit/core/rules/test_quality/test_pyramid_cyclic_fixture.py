"""Unit test: cyclic fixture graph terminates (pure ast parsing, no I/O)."""

from __future__ import annotations

import ast
import textwrap

from axm_audit.core.rules.test_quality._shared import fixture_does_io

__all__: list[str] = []


def test_cyclic_fixture_graph_terminates() -> None:
    """AC3: cyclic fixture graph terminates via visited-set short-circuit."""
    src = textwrap.dedent(
        """
        def fix_a(fix_b):
            return fix_b

        def fix_b(fix_a):
            return fix_a
        """
    )
    tree = ast.parse(src)
    fixtures = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    visited: set[str] = set()

    result = fixture_does_io("fix_a", fixtures, visited, 0)

    assert result is False
    assert "fix_a" in visited
    assert "fix_b" in visited
