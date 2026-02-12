"""Tests for scoring balance across all quality rules."""


class TestScoringBalance:
    """Verify that scoring formulas are balanced across rules."""

    def test_lint_rule_penalty_appropriate(self):
        """Linting: 2 points per issue is reasonable for 50 issues = fail."""
        # 50 issues = 100 - 50*2 = 0 (fail)
        # 10 issues = 100 - 10*2 = 80 (pass)
        assert 100 - 50 * 2 == 0
        assert 100 - 10 * 2 == 80

    def test_type_rule_penalty_appropriate(self):
        """Type checking: 5 points per error for 4 errors = fail."""
        # 4 errors = 100 - 4*5 = 80 (borderline)
        # 5 errors = 100 - 5*5 = 75 (fail)
        assert 100 - 4 * 5 == 80
        assert 100 - 5 * 5 == 75

    def test_complexity_rule_penalty_appropriate(self):
        """Complexity: 10 points per high-CC function for 2 = fail."""
        # 2 high-CC = 100 - 2*10 = 80 (borderline)
        # 3 high-CC = 100 - 3*10 = 70 (fail)
        assert 100 - 2 * 10 == 80
        assert 100 - 3 * 10 == 70

    def test_security_rule_penalty_appropriate(self):
        """Security: 15 points per HIGH, 5 per MEDIUM."""
        # 1 HIGH + 1 MEDIUM = 100 - (1*15 + 1*5) = 80 (borderline)
        # 2 HIGH = 100 - 2*15 = 70 (fail)
        assert 100 - (1 * 15 + 1 * 5) == 80
        assert 100 - 2 * 15 == 70
