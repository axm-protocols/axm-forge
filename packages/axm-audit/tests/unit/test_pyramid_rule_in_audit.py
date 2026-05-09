from __future__ import annotations

import pytest

from axm_audit.core.auditor import get_rules_for_category
from axm_audit.core.rules.structure import TestsPyramidRule

__all__ = []

pytestmark = pytest.mark.integration


def test_pyramid_rule_registered_in_structure_category() -> None:
    rules = get_rules_for_category("structure")
    assert any(isinstance(r, TestsPyramidRule) for r in rules)
