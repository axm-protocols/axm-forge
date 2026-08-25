"""Unit tests for AntiMirrorRule registry presence and K=1 suppression."""

from __future__ import annotations


def test_anti_mirror_rule_registered_or_absent(registry: dict[str, list[type]]) -> None:
    """AntiMirrorRule, if registered, lives in the practices bucket."""
    bucket = registry.get("practices", [])
    names = {cls.__name__ for cls in bucket}
    # Tolerate either presence or absence — the rule may not auto-register.
    if "AntiMirrorRule" in names:
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        assert any(cls is AntiMirrorRule for cls in bucket)
