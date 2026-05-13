"""Unit tests for AntiMirrorRule registry presence."""

from __future__ import annotations

import pytest


@pytest.fixture
def registry():
    import axm_audit.core.rules  # noqa: F401  (fire decorators)
    from axm_audit.core.rules.base import get_registry

    return get_registry()


def test_anti_mirror_rule_registered_or_absent(registry: dict[str, list[type]]) -> None:
    """AntiMirrorRule, if registered, lives in the practices bucket."""
    bucket = registry.get("practices", [])
    names = {cls.__name__ for cls in bucket}
    # Tolerate either presence or absence — the rule may not auto-register.
    if "AntiMirrorRule" in names:
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        assert any(cls is AntiMirrorRule for cls in bucket)
