"""Tests for base module — ProjectRule ABC and scoring constants."""

from __future__ import annotations

import pytest


class TestProjectRule:
    """Tests for ProjectRule ABC."""

    def test_is_abstract(self) -> None:
        """ProjectRule cannot be instantiated directly."""
        from axm_audit.core.rules.base import ProjectRule

        with pytest.raises(TypeError):
            ProjectRule()  # type: ignore[abstract]

    def test_has_rule_id_property(self) -> None:
        """ProjectRule declares abstract rule_id property."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "rule_id")

    def test_has_check_method(self) -> None:
        """ProjectRule declares abstract check method."""
        from axm_audit.core.rules.base import ProjectRule

        assert hasattr(ProjectRule, "check")


class TestScoringConstants:
    """Tests for shared scoring constants."""

    def test_pass_threshold_value(self) -> None:
        """PASS_THRESHOLD should be 90."""
        from axm_audit.core.rules.base import PASS_THRESHOLD

        assert PASS_THRESHOLD == 90

    def test_complexity_threshold_value(self) -> None:
        """COMPLEXITY_THRESHOLD should be 10."""
        from axm_audit.core.rules.base import COMPLEXITY_THRESHOLD

        assert COMPLEXITY_THRESHOLD == 10

    def test_perfect_score_value(self) -> None:
        """PERFECT_SCORE should be 100."""
        from axm_audit.core.rules.base import PERFECT_SCORE

        assert PERFECT_SCORE == 100
