"""Integration tests for CouplingMetricRule scoring formula (real filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
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
        score = result.score
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
        assert result.score == 94  # 100 - 2*3 (warnings)

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
        assert result.score == 0

    def test_no_src_returns_100(self, tmp_path: Path) -> None:
        """No src/ directory → score=100."""
        from axm_audit.core.rules.architecture import CouplingMetricRule

        rule = CouplingMetricRule()
        result = rule.check(tmp_path)
        assert result.score == 100

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
        assert result.score == 100
