"""Unit tests for the declared-but-unimplemented node test-quality rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.node.test_quality import (
    NodeTestDuplicateRule,
    NodeTestMirrorRule,
    NodeTestPyramidRule,
    NodeTestTautologyRule,
)

_PLACEHOLDERS = [
    NodeTestMirrorRule,
    NodeTestPyramidRule,
    NodeTestTautologyRule,
    NodeTestDuplicateRule,
]


@pytest.mark.parametrize("rule_cls", _PLACEHOLDERS)
def test_placeholder_never_false_greens(rule_cls: type, tmp_path: Path) -> None:
    """A not-implemented rule must not inflate the score (score is None).

    It reports INFO with ``score=None`` so it is neither a real pass (100) nor
    a fail — it simply does not contribute to the quality score until the TS
    AST work lands.
    """
    result = rule_cls().check(tmp_path)
    assert result.score is None


@pytest.mark.parametrize("rule_cls", _PLACEHOLDERS)
def test_placeholder_names_the_missing_dependency(
    rule_cls: type, tmp_path: Path
) -> None:
    """The result must say it is not implemented and name the TS-AST need."""
    result = rule_cls().check(tmp_path)
    assert "not implemented" in result.message.lower()
    assert "ast" in (result.fix_hint or "").lower()
