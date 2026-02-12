"""Tests for coupling metric fix and scoring integration."""

import ast
from pathlib import Path

import pytest

from axm_audit.models.results import AuditResult, CheckResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_check(rule_id: str, score: float) -> CheckResult:
    """Helper to create a CheckResult with a score."""
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="",
        details={"score": score},
    )


# ---------------------------------------------------------------------------
# 1. _extract_imports fix: count modules, not symbols
# ---------------------------------------------------------------------------


class TestExtractImports:
    """Tests for _extract_imports counting modules not symbols."""

    def test_from_import_counts_module_not_symbols(self) -> None:
        """'from foo import A, B, C' = 1 import, not 4."""
        from axm_audit.core.rules.architecture import _extract_imports

        code = "from axm_init.models import CheckResult, Severity, Config"
        tree = ast.parse(code)
        imports = _extract_imports(tree)
        # Should be just ["axm_init.models"], not 4 entries
        assert len(imports) == 1
        assert imports[0] == "axm_init.models"

    def test_plain_import(self) -> None:
        """'import os' = 1 import."""
        from axm_audit.core.rules.architecture import _extract_imports

        tree = ast.parse("import os")
        imports = _extract_imports(tree)
        assert imports == ["os"]

    def test_relative_import_no_module(self) -> None:
        """'from . import x' (module=None) produces 0 imports."""
        from axm_audit.core.rules.architecture import _extract_imports

        tree = ast.parse("from . import x")
        imports = _extract_imports(tree)
        assert imports == []

    def test_multiple_imports(self) -> None:
        """Multiple distinct import statements are counted separately."""
        from axm_audit.core.rules.architecture import _extract_imports

        code = "import os\nimport sys\nfrom pathlib import Path"
        tree = ast.parse(code)
        imports = _extract_imports(tree)
        assert set(imports) == {"os", "sys", "pathlib"}


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
        score = result.details["score"]
        assert score == 100
        assert result.details["n_over_threshold"] == 0

    def test_some_above_threshold(self, tmp_path: Path) -> None:
        """2 modules above threshold → score=90."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        # a=5 (under), b=12 (over), c=15 (over)
        (src / "a.py").write_text("\n".join(f"import m{i}" for i in range(5)))
        (src / "b.py").write_text("\n".join(f"import m{i}" for i in range(12)))
        (src / "c.py").write_text("\n".join(f"import m{i}" for i in range(15)))
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details["n_over_threshold"] == 2
        assert result.details["score"] == 90  # 100 - 2*5

    def test_many_above_threshold_floors_at_zero(self, tmp_path: Path) -> None:
        """20+ modules above threshold → score=0."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule(fan_out_threshold=10)
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        for i in range(25):
            (src / f"mod_{i}.py").write_text(
                "\n".join(f"import dep_{j}" for j in range(15))
            )
        (src / "__init__.py").write_text("")

        result = rule.check(tmp_path)
        assert result.details["score"] == 0

    def test_no_src_returns_100(self, tmp_path: Path) -> None:
        """No src/ directory → score=100."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
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
        over = result.details["over_threshold"]
        assert len(over) == 1
        assert over[0]["fan_out"] == 15
        assert "big" in over[0]["module"]


# ---------------------------------------------------------------------------
# 3. Scoring weights: arch (10%) + practices (5%) in total
# ---------------------------------------------------------------------------


class TestScoringWeights:
    """Tests for the 8-category weighted scoring."""

    def test_weights_sum_to_one(self) -> None:
        """All weights must sum to 1.0."""
        # After the change, weights include architecture + practices
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
        # All 100 → total must be 100
        assert result.quality_score == pytest.approx(100.0, abs=0.1)

    def test_architecture_counts_in_score(self) -> None:
        """ARCH_COUPLING score affects the total."""
        # All 100 except architecture = 0
        checks = [
            _make_check("QUALITY_LINT", 100),
            _make_check("QUALITY_TYPE", 100),
            _make_check("QUALITY_COMPLEXITY", 100),
            _make_check("QUALITY_SECURITY", 100),
            _make_check("DEPS_AUDIT", 100),
            _make_check("QUALITY_COVERAGE", 100),
            _make_check("ARCH_COUPLING", 0),  # 0 * 10% = -10
            _make_check("PRACTICE_DOCSTRING", 100),
            _make_check("PRACTICE_BARE_EXCEPT", 100),
            _make_check("PRACTICE_SECURITY", 100),
        ]
        result = AuditResult(checks=checks)
        # Missing 10% from architecture
        assert result.quality_score == pytest.approx(90.0, abs=0.1)

    def test_practices_counts_in_score(self) -> None:
        """PRACTICE_* scores affect the total."""
        checks = [
            _make_check("QUALITY_LINT", 100),
            _make_check("QUALITY_TYPE", 100),
            _make_check("QUALITY_COMPLEXITY", 100),
            _make_check("QUALITY_SECURITY", 100),
            _make_check("DEPS_AUDIT", 100),
            _make_check("QUALITY_COVERAGE", 100),
            _make_check("ARCH_COUPLING", 100),
            _make_check("PRACTICE_DOCSTRING", 0),  # avg(0,100,100)=66.7 * 5%
            _make_check("PRACTICE_BARE_EXCEPT", 100),
            _make_check("PRACTICE_SECURITY", 100),
        ]
        result = AuditResult(checks=checks)
        # 95% at 100 + 5% at 66.7 = 95 + 3.3 = 98.3
        assert result.quality_score == pytest.approx(98.3, abs=0.1)
