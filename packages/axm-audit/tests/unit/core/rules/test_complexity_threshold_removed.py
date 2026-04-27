from __future__ import annotations


def test_no_complexity_threshold_constant():
    """AC4: ``COMPLEXITY_THRESHOLD`` must be removed from rules.base."""
    from axm_audit.core.rules import base

    assert not hasattr(base, "COMPLEXITY_THRESHOLD")
