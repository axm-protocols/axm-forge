"""Unit tests for axm_ast.core.analyzer."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.dead_code import find_dead_code

_AXM_AST_ROOT = Path(__file__).resolve().parents[3]


def test_describe_data_not_reported_dead() -> None:
    """After the patch, axm-ast's _DescribeData is no longer flagged."""
    pkg = analyze_package(_AXM_AST_ROOT)
    dead = find_dead_code(pkg)
    assert "_DescribeData" not in {d.name for d in dead}
