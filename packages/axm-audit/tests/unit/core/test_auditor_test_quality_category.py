from __future__ import annotations

import pytest

from axm_audit.core.auditor import get_rules_for_category


def test_get_rules_for_category_test_quality_empty_ok() -> None:
    """test_quality is a valid category and returns a list of registered rules."""
    rules = get_rules_for_category("test_quality")
    assert isinstance(rules, list)
    assert all(hasattr(r, "check") for r in rules), (
        "Every test_quality rule must expose a `.check` method"
    )


def test_get_rules_for_category_test_quality_picks_up_registrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rules registered under test_quality are surfaced by get_rules_for_category."""
    from axm_audit.core import auditor as auditor_module
    from axm_audit.core.rules.quality import LintingRule

    fake_registry = {"test_quality": [LintingRule]}
    monkeypatch.setattr(auditor_module, "get_registry", lambda: fake_registry)

    rules = get_rules_for_category("test_quality")

    assert len(rules) >= 1
