"""Unit tests for axm_edit.core.anchor_rules (no real I/O)."""

from __future__ import annotations

from axm_edit.core.anchor_rules import ANCHOR_RULES_HINT

ANCHOR_RULE_MARKERS = (
    "trailing newline",
    "syntax gate",
    "whole line",
    "indentation",
)


class TestAnchorRulesHint:
    """AC1: the shared constant publishes the anchor contract."""

    def test_hint_is_a_non_empty_string_constant(self) -> None:
        """AC1: ANCHOR_RULES_HINT is a non-empty module-level string."""
        assert isinstance(ANCHOR_RULES_HINT, str)
        assert ANCHOR_RULES_HINT.strip()

    def test_hint_states_the_anchor_contract(self) -> None:
        """AC1: the constant names the contract markers."""
        lowered = ANCHOR_RULES_HINT.lower()
        missing = [marker for marker in ANCHOR_RULE_MARKERS if marker not in lowered]

        assert not missing, f"missing rule markers: {missing}"
