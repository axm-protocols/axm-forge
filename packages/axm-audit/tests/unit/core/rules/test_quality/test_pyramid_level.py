"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core) and helpers.

Merged from:
- test_pyramid_level_core.py (rule registration + classify_level table)
- test_pyramid_cyclic_fixture.py (fixture cycle termination via _shared)
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality._shared import fixture_does_io
from axm_audit.core.rules.test_quality.pyramid_level import (
    PyramidLevelRule,
    classify_level,
)


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    classes = {item if isinstance(item, type) else type(item) for item in bucket}
    assert PyramidLevelRule in classes


@pytest.mark.parametrize(
    ("has_real_io", "has_subprocess", "imports_public", "imports_internal", "expected"),
    [
        (False, True, False, False, "e2e"),
        (True, True, True, True, "e2e"),
        (False, False, True, False, "unit"),
        (True, False, True, False, "integration"),
        (True, False, False, True, "integration"),
        (True, False, False, False, "integration"),
        (False, False, False, True, "unit"),
        (False, False, False, False, "unit"),
    ],
)
def test_classify_level_8_branches_table_driven(
    has_real_io: bool,
    has_subprocess: bool,
    imports_public: bool,
    imports_internal: bool,
    expected: str,
) -> None:
    level, reason = classify_level(
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        imports_public=imports_public,
        imports_internal=imports_internal,
    )
    assert level == expected
    assert reason


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
