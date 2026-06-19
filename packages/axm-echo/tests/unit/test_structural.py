"""Unit tests for axm_echo.structural — pure AST structural similarity.

Covers the move (AXM-2172 / E5) of the structural-similarity helpers from
axm-audit's duplicate_tests rule into axm-echo's public surface. All paths
are 100% structural: no embedding backend, no torch (AC3).
"""

from __future__ import annotations

import ast
import sys

import pytest

from axm_echo.structural import jaccard_similarity, statement_set


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param({"x", "y", "z"}, {"x", "y", "z"}, 1.0, id="identical_sets"),
        pytest.param({"a", "b"}, {"c", "d"}, 0.0, id="disjoint_sets"),
    ],
)
def test_jaccard_extremes(a: set[str], b: set[str], expected: float) -> None:
    """AC1: Jaccard is 1.0 for identical sets, 0.0 for disjoint sets."""
    assert jaccard_similarity(a, b) == expected


def test_statement_set_normalizes_constants() -> None:
    """AC1: statement_set normalizes literal constants and name ids.

    Two functions whose bodies differ only by their literal constants and
    variable identifiers must produce the SAME normalized statement-set,
    because the normalization replaces ``Constant(...)``/``Name(...)`` payloads.
    """
    src_a = "def f():\n    foo = 1\n    assert foo == 2\n"
    src_b = "def g():\n    bar = 99\n    assert bar == 7\n"
    node_a = ast.parse(src_a).body[0]
    node_b = ast.parse(src_b).body[0]
    assert isinstance(node_a, ast.FunctionDef)
    assert isinstance(node_b, ast.FunctionDef)

    set_a = statement_set(node_a)
    set_b = statement_set(node_b)

    # Normalization erases constant/name identity → identical structural sets.
    assert set_a == set_b
    # And the normalized markers are present, not the raw literals.
    blob = "".join(set_a)
    assert "Constant(<C>)" in blob
    assert "99" not in blob
    assert "bar" not in blob


def test_no_torch_on_structural_path() -> None:
    """AC3: exercising the structural path never imports torch."""
    sys.modules.pop("torch", None)
    node = ast.parse("def f():\n    x = 1\n    return x\n").body[0]
    assert isinstance(node, ast.FunctionDef)

    stmt_set = statement_set(node)
    jaccard_similarity(stmt_set, stmt_set)

    assert "torch" not in sys.modules
