"""Unit tests for MirrorRule (pure)."""

from __future__ import annotations

import pytest

from axm_audit.core.rules.practices.mirror import MirrorRule


class TestMirrorRuleUnit:
    """Tests for MirrorRule (pure)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_TEST_MIRROR."""
        rule = MirrorRule()
        assert rule.rule_id == "PRACTICE_TEST_MIRROR"


@pytest.fixture
def registry():
    import axm_audit.core.rules  # noqa: F401  (fire decorators)
    from axm_audit.core.rules.base import get_registry

    return get_registry()


def test_mirror_rule_registered(registry: dict[str, list[type]]) -> None:
    """MirrorRule must be registered in the practices bucket."""
    bucket = registry["practices"]
    names = {cls.__name__ for cls in bucket}
    assert "MirrorRule" in names
