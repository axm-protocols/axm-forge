"""Audit test: ``tools/impact.py`` contains no ``assert`` statements.

AC1 + AC5: the production module must not rely on ``assert`` for control
flow or type narrowing, since ``python -O`` strips them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import axm_ast

IMPACT_PATH = Path(axm_ast.__file__).resolve().parent / "tools" / "impact.py"


@pytest.mark.integration
def test_tools_impact_contains_no_assert_statement() -> None:
    """Parse the module and assert no ``ast.Assert`` node exists."""
    source = IMPACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(IMPACT_PATH))

    asserts = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]

    assert not asserts, (
        f"{IMPACT_PATH} still contains "
        f"{len(asserts)} assert statement(s) at lines: "
        f"{[node.lineno for node in asserts]}"
    )
