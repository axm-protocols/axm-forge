"""Tests for coupling metric fix and scoring integration."""

import ast

import pytest
from _registry_helpers import build_rule_category_map

from axm_audit.models.results import AuditResult, CheckResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RULE_CATEGORY = build_rule_category_map()


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Helper to create a CheckResult with a score and category."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        score=int(score),
        category=_RULE_CATEGORY.get(rule_id),
    )


# ---------------------------------------------------------------------------
# 1. _extract_imports fix: count modules, not symbols
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for _extract_imports counting modules not symbols."""

    def test_from_import_counts_module_not_symbols(self) -> None:
        """'from foo import A, B, C' = 1 import, not 4."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        code = "from axm_init.models import CheckResult, Severity, Config"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        # Should be just ["axm_init.models"], not 4 entries
        assert len(imports) == 1
        assert imports[0] == "axm_init.models"

    def test_plain_import(self) -> None:
        """'import os' = 1 import."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        tree = ast.parse("import os")
        imports = extract_imports(tree)
        assert imports == ["os"]

    def test_relative_import_no_module(self) -> None:
        """'from . import x' (module=None) produces 0 imports."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        tree = ast.parse("from . import x")
        imports = extract_imports(tree)
        assert imports == []

    def test_multiple_imports(self) -> None:
        """Multiple distinct import statements are counted separately."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        code = "import os\nimport sys\nfrom pathlib import Path"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert set(imports) == {"os", "sys", "pathlib"}

    def test_future_import_excluded(self) -> None:
        """'from __future__ import annotations' is a directive, not a dependency."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        code = "from __future__ import annotations\nimport os\nfrom pathlib import Path"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert "__future__" not in imports
        assert set(imports) == {"os", "pathlib"}

    def test_future_import_only(self) -> None:
        """Module with only __future__ import has 0 fan-out."""
        from axm_audit.core.rules.architecture.coupling import extract_imports

        code = "from __future__ import annotations"
        tree = ast.parse(code)
        imports = extract_imports(tree)
        assert imports == []


# ---------------------------------------------------------------------------
# 3. Scoring integration: rule_id -> category routing actually contributes
# ---------------------------------------------------------------------------


class TestScoringIntegration:
    """End-to-end checks that registered rule IDs route to scored categories.

    These tests verify integration (registry wiring + AuditResult.quality_score)
    without hardcoding the weights table — they only assert structural
    properties (perfect=100, monotonicity).
    """

    def test_perfect_scores_yield_100(self) -> None:
        """Every scored category at 100 → composite is 100."""
        checks = [
            _make_check("QUALITY_LINT", 100),
            _make_check("QUALITY_TYPE", 100),
            _make_check("QUALITY_COMPLEXITY", 100),
            _make_check("QUALITY_SECURITY", 100),
            _make_check("DEPS_AUDIT", 100),
            _make_check("QUALITY_COVERAGE", 100),
            _make_check("ARCH_COUPLING", 100),
            _make_check("PRACTICE_DOCSTRING", 100),
        ]
        result = AuditResult(checks=checks)
        assert result.quality_score == pytest.approx(100.0, abs=0.1)

    @pytest.mark.parametrize(
        "rule_id",
        [
            pytest.param("ARCH_COUPLING", id="architecture"),
            pytest.param("PRACTICE_DOCSTRING", id="practices"),
        ],
    )
    def test_rule_failure_lowers_composite(self, rule_id: str) -> None:
        """A rule dropping from 100 to 0 must lower the composite score."""
        baseline = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check(rule_id, 100),
            ]
        )
        degraded = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check(rule_id, 0),
            ]
        )
        assert baseline.quality_score is not None
        assert degraded.quality_score is not None
        assert degraded.quality_score < baseline.quality_score

    def test_practice_security_routes_to_security_category(self) -> None:
        """PRACTICE_SECURITY is registered under 'security' (not 'practices').

        Regression guard: a renaming or registry refactor must not silently
        re-route this rule. We check the registry mapping directly.
        """
        assert _RULE_CATEGORY.get("PRACTICE_SECURITY") == "security"
