"""Tests for Quality Rules — RED phase."""

from pathlib import Path


class TestLintingRule:
    """Tests for LintingRule (ruff integration)."""

    def test_clean_project_high_score(self, tmp_path: Path) -> None:
        """Clean project should score 100."""
        from axm_audit.core.rules.quality import LintingRule

        # Create minimal clean Python file
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package init."""\n')
        (src / "main.py").write_text(
            '"""Main module."""\n\n'
            "def hello() -> str:\n"
            '    """Return greeting."""\n'
            '    return "hello"\n'
        )

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] == 100

    def test_issues_reduce_score(self, tmp_path: Path) -> None:
        """Lint issues should reduce score."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        # Create file with lint issues (unused import)
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] < 100
        assert result.details["issue_count"] > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_LINT."""
        from axm_audit.core.rules.quality import LintingRule

        rule = LintingRule()
        assert rule.rule_id == "QUALITY_LINT"


class TestTypeCheckRule:
    """Tests for TypeCheckRule (mypy integration)."""

    def test_typed_project_high_score(self, tmp_path: Path) -> None:
        """Fully typed project should score near 100."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] >= 80

    def test_type_errors_reduce_score(self, tmp_path: Path) -> None:
        """Type errors should reduce score."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        # Create file with type error
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["error_count"] > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_TYPE."""
        from axm_audit.core.rules.quality import TypeCheckRule

        rule = TypeCheckRule()
        assert rule.rule_id == "QUALITY_TYPE"


class TestComplexityRule:
    """Tests for ComplexityRule (radon integration)."""

    def test_simple_functions_high_score(self, tmp_path: Path) -> None:
        """Simple functions should score high."""
        from axm_audit.core.rules.quality import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complex_functions_reduce_score(self, tmp_path: Path) -> None:
        """High complexity functions should reduce score."""
        from axm_audit.core.rules.quality import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        # Create function with CC > 10 (threshold for high complexity)
        complex_code = """
def complex_fn(x: int, y: int, z: int) -> str:
    if x > 0:
        if x > 10:
            if x > 100:
                if y > 0:
                    return "huge_pos"
                else:
                    return "huge_neg"
            elif x > 50:
                return "large"
            else:
                return "medium"
        elif x > 5:
            return "small"
        else:
            return "tiny"
    elif x < 0:
        if x < -10:
            if z > 0:
                return "neg_large_z"
            else:
                return "neg_large"
        else:
            return "neg_small"
    else:
        if y > 0 and z > 0:
            return "zero_both"
        elif y > 0:
            return "zero_y"
        return "zero"
"""
        (src / "complex.py").write_text(complex_code)

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["high_complexity_count"] > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_COMPLEXITY."""
        from axm_audit.core.rules.quality import ComplexityRule

        rule = ComplexityRule()
        assert rule.rule_id == "QUALITY_COMPLEXITY"


class TestAuditResultScoring:
    """Tests for AuditResult quality_score and grade."""

    def test_quality_score_weighted_average(self) -> None:
        """quality_score uses 40/35/25 weights."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="",
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="",
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="",
                    details={"score": 100},
                ),
            ]
        )
        assert result.quality_score == 100.0

    def test_quality_score_partial(self) -> None:
        """quality_score with mixed scores."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="",
                    details={"score": 80},  # 80 * 0.40 = 32
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="",
                    details={"score": 60},  # 60 * 0.35 = 21
                ),
                CheckResult(
                    rule_id="QUALITY_COMPLEXITY",
                    passed=True,
                    message="",
                    details={"score": 100},  # 100 * 0.25 = 25
                ),
            ]
        )
        # 32 + 21 + 25 = 78
        assert result.quality_score == 78.0

    def test_quality_score_none_without_quality_checks(self) -> None:
        """quality_score is None if no quality checks present."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(rule_id="FILE_EXISTS_README.md", passed=True, message=""),
            ]
        )
        assert result.quality_score is None

    def test_grade_thresholds(self) -> None:
        """Grade boundaries: A>=90, B>=80, C>=70, D>=60, F<60."""
        from axm_audit.models.results import AuditResult, CheckResult

        def make_result(score: float) -> AuditResult:
            return AuditResult(
                checks=[
                    CheckResult(
                        rule_id="QUALITY_LINT",
                        passed=True,
                        message="",
                        details={"score": score},
                    ),
                    CheckResult(
                        rule_id="QUALITY_TYPE",
                        passed=True,
                        message="",
                        details={"score": score},
                    ),
                    CheckResult(
                        rule_id="QUALITY_COMPLEXITY",
                        passed=True,
                        message="",
                        details={"score": score},
                    ),
                ]
            )

        assert make_result(95).grade == "A"
        assert make_result(85).grade == "B"
        assert make_result(75).grade == "C"
        assert make_result(65).grade == "D"
        assert make_result(50).grade == "F"

    def test_grade_none_without_quality_score(self) -> None:
        """grade is None if quality_score is None."""
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(rule_id="FILE_EXISTS_README.md", passed=True, message=""),
            ]
        )
        assert result.grade is None
