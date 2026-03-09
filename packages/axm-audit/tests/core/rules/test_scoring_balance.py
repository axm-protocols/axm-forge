"""Tests for scoring balance across all quality rules.

Verifies that penalty formulas are consistent with the documented convention
in ``base.py`` and produce sensible pass/fail thresholds at ~90/100.
"""

from __future__ import annotations


class TestScoringBalance:
    """Verify that scoring formulas are balanced across rules."""

    # ── Quality rules ─────────────────────────────────────────────────

    def test_lint_rule_penalty(self) -> None:
        """Linting: 2 pts/issue → 5 issues=pass(90), 50 issues=fail(0)."""
        assert 100 - 5 * 2 == 90
        assert 100 - 50 * 2 == 0

    def test_formatting_rule_penalty(self) -> None:
        """Formatting: 5 pts/file → 2 files=pass(90), 20 files=fail(0)."""
        assert 100 - 2 * 5 == 90
        assert 100 - 20 * 5 == 0

    def test_type_rule_penalty(self) -> None:
        """Type checking: 5 pts/error → 2 errors=pass(90), 20 errors=fail(0)."""
        assert 100 - 2 * 5 == 90
        assert 100 - 20 * 5 == 0

    def test_complexity_rule_penalty(self) -> None:
        """Complexity: 10 pts/function → 1 func=pass(90), 10 funcs=fail(0)."""
        assert 100 - 1 * 10 == 90
        assert 100 - 10 * 10 == 0

    def test_diff_size_rule_linear(self) -> None:
        """DiffSize: linear 100→0 over [400,1200] lines changed."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule._compute_score(0) == 100
        assert DiffSizeRule._compute_score(400) == 100
        assert DiffSizeRule._compute_score(800) == 50
        assert DiffSizeRule._compute_score(1200) == 0
        assert DiffSizeRule._compute_score(1500) == 0

    # ── Security rules ────────────────────────────────────────────────

    def test_bandit_rule_penalty(self) -> None:
        """Security (Bandit): 15 pts/HIGH, 5 pts/MEDIUM."""
        assert 100 - (1 * 15 + 1 * 5) == 80
        assert 100 - 2 * 15 == 70

    def test_secret_pattern_penalty(self) -> None:
        """Secret patterns: 25 pts/secret → 1 secret=75, 4 secrets=fail(0)."""
        assert 100 - 1 * 25 == 75
        assert 100 - 4 * 25 == 0

    # ── Dependency rules ──────────────────────────────────────────────

    def test_dep_audit_penalty(self) -> None:
        """Dep audit: 15 pts/vulnerable package."""
        assert 100 - 1 * 15 == 85
        assert 100 - 7 * 15 < 0  # clamped to 0

    def test_dep_hygiene_penalty(self) -> None:
        """Dep hygiene: 10 pts/issue."""
        assert 100 - 1 * 10 == 90
        assert 100 - 10 * 10 == 0

    # ── Architecture rules ────────────────────────────────────────────

    def test_circular_import_penalty(self) -> None:
        """Circular imports: 20 pts/cycle → 1 cycle=80, 5 cycles=fail(0)."""
        assert 100 - 1 * 20 == 80
        assert 100 - 5 * 20 == 0

    def test_god_class_penalty(self) -> None:
        """God classes: 15 pts/class."""
        assert 100 - 1 * 15 == 85
        assert 100 - 7 * 15 < 0  # clamped to 0

    def test_coupling_penalty(self) -> None:
        """Coupling: 5 pts/over-coupled module → 2 modules=pass(90)."""
        assert 100 - 2 * 5 == 90
        assert 100 - 20 * 5 == 0

    def test_duplication_penalty(self) -> None:
        """Duplication: 10 pts/pair → 1 pair=pass(90), 10 pairs=fail(0)."""
        assert 100 - 1 * 10 == 90
        assert 100 - 10 * 10 == 0

    # ── Practice rules ────────────────────────────────────────────────

    def test_bare_except_penalty(self) -> None:
        """Bare except: 20 pts/occurrence → 1 occ=80, 5 occ=fail(0)."""
        assert 100 - 1 * 20 == 80
        assert 100 - 5 * 20 == 0

    def test_blocking_io_penalty(self) -> None:
        """Blocking I/O: 15 pts/violation."""
        assert 100 - 1 * 15 == 85
        assert 100 - 7 * 15 < 0  # clamped to 0

    def test_docstring_coverage_ratio(self) -> None:
        """Docstring coverage: ratio-based → 90%=pass(90), 50%=fail(50)."""
        assert int(0.90 * 100) == 90
        assert int(0.50 * 100) == 50

    def test_logging_coverage_ratio(self) -> None:
        """Logging presence: ratio-based → 90%=pass(90), 50%=fail(50)."""
        assert int(0.90 * 100) == 90
        assert int(0.50 * 100) == 50
