"""Tests for coupling metric fix and scoring integration."""

import ast
from pathlib import Path

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
        details={"score": score},
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
# 2. Coupling formula: 100 - N(>10) * 5
# ---------------------------------------------------------------------------


class TestCouplingFormula:
    """Tests for the new coupling scoring formula."""

    def test_all_below_threshold(self, tmp_path: Path) -> None:
        """All modules below threshold → score=100, n_over=0."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # Create 3 modules with < 10 imports each
        for name, n_imports in [("a", 3), ("b", 5), ("c", 8)]:
            imports = "\n".join(f"import mod_{i}" for i in range(n_imports))
            (src / f"{name}.py").write_text(imports)
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        score = result.details["score"]
        assert score == 100
        assert result.details["n_over_threshold"] == 0

    def test_some_above_threshold(self, tmp_path: Path) -> None:
        """2 modules above threshold (both warnings) → score=94."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # a=5 (under), b=12 (warning), c=15 (warning)
        # default multiplier=2 → error threshold=20, both under
        (src / "a.py").write_text("\n".join(f"import m{i}" for i in range(5)))
        (src / "b.py").write_text("\n".join(f"import m{i}" for i in range(12)))
        (src / "c.py").write_text("\n".join(f"import m{i}" for i in range(15)))
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["n_over_threshold"] == 2
        assert result.details["score"] == 94  # 100 - 2*3 (warnings)

    def test_many_above_threshold_floors_at_zero(self, tmp_path: Path) -> None:
        """Many modules above threshold → score floors at 0."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # fan-out=25, threshold=10, multiplier=2 → error threshold=20
        # 25 > 20 → all ERROR → 100 - 25*5 = 0 (floored)
        for i in range(25):
            (src / f"mod_{i}.py").write_text(
                "\n".join(f"import dep_{j}" for j in range(25))
            )
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] == 0

    def test_no_src_returns_100(self, tmp_path: Path) -> None:
        """No src/ directory → score=100."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] == 100

    def test_over_threshold_lists_modules(self, tmp_path: Path) -> None:
        """Details lists which modules exceed threshold."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        (src / "ok.py").write_text("import os")
        (src / "big.py").write_text("\n".join(f"import m{i}" for i in range(15)))
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details is not None
        over = result.details["over_threshold"]
        assert len(over) == 1
        assert over[0]["fan_out"] == 15
        assert "big" in over[0]["module"]

    def test_init_py_excluded_from_coupling(self, tmp_path: Path) -> None:
        """__init__.py re-export files are exempt from fan-out analysis.

        Their purpose is to aggregate submodule exports, so high fan-out
        is structural — not a coupling smell.
        """
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=5)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # __init__.py with 10 re-exports — should be ignored
        init_imports = "\n".join(f"from pkg.sub_{i} import X{i}" for i in range(10))
        (src / "__init__.py").write_text(init_imports)

        # Regular module with 3 imports — under threshold
        (src / "core.py").write_text("import os\nimport sys\nimport json")

        result = rule.check(tmp_path)
        assert result.details is not None
        # __init__.py excluded → only core.py counted (3 imports, under 5)
        assert result.details["n_over_threshold"] == 0
        assert result.details["score"] == 100


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

    def test_architecture_failure_lowers_composite(self) -> None:
        """ARCH_COUPLING=0 with rest at 100 must produce score < 100."""
        baseline = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check("ARCH_COUPLING", 100),
            ]
        )
        degraded = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check("ARCH_COUPLING", 0),
            ]
        )
        assert baseline.quality_score is not None
        assert degraded.quality_score is not None
        assert degraded.quality_score < baseline.quality_score

    def test_practices_failure_lowers_composite(self) -> None:
        """PRACTICE_DOCSTRING=0 lowers the composite below baseline."""
        baseline = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check("PRACTICE_DOCSTRING", 100),
            ]
        )
        degraded = AuditResult(
            checks=[
                _make_check("QUALITY_LINT", 100),
                _make_check("PRACTICE_DOCSTRING", 0),
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
