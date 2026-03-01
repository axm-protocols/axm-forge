"""Tests for Quality Rules — RED phase."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from axm_audit.core.rules.dead_code import DeadCodeRule
    from axm_audit.models.results import CheckResult


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

    def test_lint_details_has_issues_key(self, tmp_path: Path) -> None:
        """details must contain an 'issues' key with a list."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package init."""\n')

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert "issues" in result.details
        assert isinstance(result.details["issues"], list)

    def test_lint_issues_match_count(self, tmp_path: Path) -> None:
        """len(details['issues']) must equal issue_count (up to cap of 20)."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        expected = min(result.details["issue_count"], 20)
        assert len(result.details["issues"]) == expected

    def test_lint_issue_entry_schema(self, tmp_path: Path) -> None:
        """Each issue entry must have file, line, code, message keys."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details["issues"]:
            assert "file" in entry
            assert "line" in entry
            assert "code" in entry
            assert "message" in entry


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

    def test_typecheck_includes_tests_dir(self, tmp_path: Path) -> None:
        """TypeCheckRule should include tests/ in checked dirs when present."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_main.py").write_text(
            "def test_greet() -> None:\n    assert True\n"
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert "tests/" in result.details.get("checked", "")

    def test_typecheck_no_tests_dir(self, tmp_path: Path) -> None:
        """TypeCheckRule should work fine without tests/ directory."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )
        # No tests/ directory

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details.get("checked") == "src/"

    def test_typecheck_details_has_errors_key(self, tmp_path: Path) -> None:
        """details must contain an 'errors' key with a list."""
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
        assert "errors" in result.details
        assert isinstance(result.details["errors"], list)

    def test_typecheck_errors_match_count(self, tmp_path: Path) -> None:
        """len(details['errors']) must equal error_count."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert len(result.details["errors"]) == result.details["error_count"]

    def test_typecheck_error_entry_schema(self, tmp_path: Path) -> None:
        """Each error entry must have file, line, message, code keys."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details["errors"]:
            assert "file" in entry
            assert "line" in entry
            assert "message" in entry
            assert "code" in entry

    def test_typecheck_no_errors_empty_list(self, tmp_path: Path) -> None:
        """When no errors, details['errors'] should be []."""
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
        assert result.details["errors"] == []


class TestComplexityRule:
    """Tests for ComplexityRule (radon integration)."""

    def test_simple_functions_high_score(self, tmp_path: Path) -> None:
        """Simple functions should score high."""
        from axm_audit.core.rules.complexity import ComplexityRule

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
        from axm_audit.core.rules.complexity import ComplexityRule

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
        from axm_audit.core.rules.complexity import ComplexityRule

        rule = ComplexityRule()
        assert rule.rule_id == "QUALITY_COMPLEXITY"

    def test_complexity_rule_radon_in_project(self, tmp_path: Path) -> None:
        """When radon Python API is importable, use it directly."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complexity_rule_radon_fallback(self, tmp_path: Path) -> None:
        """When radon API is missing but radon binary exists, use subprocess."""
        import json as _json
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        # Simulate radon cc --json output for a simple function (CC=1)
        radon_output = _json.dumps(
            {
                str(src / "simple.py"): [
                    {
                        "type": "function",
                        "name": "add",
                        "complexity": 1,
                        "lineno": 1,
                        "col_offset": 0,
                        "endline": 2,
                    }
                ]
            }
        )

        mock_proc = MagicMock()
        mock_proc.stdout = radon_output
        mock_proc.returncode = 0

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value="/usr/bin/radon"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complexity_rule_radon_missing_both(self, tmp_path: Path) -> None:
        """When neither API nor binary is available, return clear error."""
        from unittest.mock import patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value=None),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert not result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] == 0
        assert result.fix_hint is not None
        assert "uv sync" in result.fix_hint

    def test_complexity_logs_oserror(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OSError from radon subprocess is logged before returning error."""
        import logging
        from unittest.mock import patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value="/usr/bin/radon"),
            patch(
                "subprocess.run",
                side_effect=OSError("mocked permission denied"),
            ),
            caplog.at_level(logging.WARNING, logger="axm_audit.core.rules.complexity"),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 0
        assert "radon cc --json failed" in caplog.text
        assert "mocked permission denied" in caplog.text

    def test_all_offenders_shown(self, tmp_path: Path) -> None:
        """top_offenders must include ALL functions with CC >= 10, not top 5."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()

        # Generate 8 distinct complex functions (each CC >= 10)
        # Uses 3 args + boolean ops + deep nesting to ensure CC > 10
        funcs: list[str] = []
        for i in range(8):
            funcs.append(
                f"def complex_{i}(x: int, y: int, z: int) -> str:\n"
                f"    if x > 0:\n"
                f"        if x > 10:\n"
                f"            if x > 100:\n"
                f"                if y > 0:\n"
                f"                    return 'a{i}'\n"
                f"                else:\n"
                f"                    return 'b{i}'\n"
                f"            elif x > 50:\n"
                f"                return 'c{i}'\n"
                f"            else:\n"
                f"                return 'd{i}'\n"
                f"        elif x > 5:\n"
                f"            return 'e{i}'\n"
                f"        else:\n"
                f"            return 'f{i}'\n"
                f"    elif x < 0:\n"
                f"        if x < -10:\n"
                f"            if z > 0:\n"
                f"                return 'g{i}'\n"
                f"            else:\n"
                f"                return 'h{i}'\n"
                f"        else:\n"
                f"            return 'i{i}'\n"
                f"    else:\n"
                f"        if y > 0 and z > 0:\n"
                f"            return 'j{i}'\n"
                f"        elif y > 0:\n"
                f"            return 'k{i}'\n"
                f"        return 'l{i}'\n\n"
            )

        (src / "many_complex.py").write_text("\n".join(funcs))

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["high_complexity_count"] == 8
        assert len(result.details["top_offenders"]) == 8


class TestAuditResultScoring:
    """Tests for AuditResult quality_score and grade (8-category model)."""

    def _make_check(self, rule_id: str, score: float) -> CheckResult:
        """Helper to create a CheckResult with a score."""
        from axm_audit.models.results import CheckResult

        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
        )

    def test_quality_score_weighted_average(self) -> None:
        """quality_score with all 8 categories at 100 → 100."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(
            checks=[
                self._make_check("QUALITY_LINT", 100),
                self._make_check("QUALITY_TYPE", 100),
                self._make_check("QUALITY_COMPLEXITY", 100),
                self._make_check("QUALITY_SECURITY", 100),
                self._make_check("DEPS_AUDIT", 100),
                self._make_check("DEPS_HYGIENE", 100),
                self._make_check("QUALITY_COVERAGE", 100),
                self._make_check("ARCH_COUPLING", 100),
                self._make_check("PRACTICE_DOCSTRING", 100),
                self._make_check("PRACTICE_BARE_EXCEPT", 100),
                self._make_check("PRACTICE_SECURITY", 100),
            ]
        )
        assert result.quality_score == 100.0

    def test_quality_score_partial(self) -> None:
        """quality_score with only lint/type/complexity → partial score."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(
            checks=[
                self._make_check("QUALITY_LINT", 80),  # 80 * 0.20 = 16
                self._make_check("QUALITY_TYPE", 60),  # 60 * 0.15 = 9
                self._make_check("QUALITY_COMPLEXITY", 100),  # 100 * 0.15 = 15
            ]
        )
        # Only 3 of 8 categories present: 16 + 9 + 15 = 40
        assert result.quality_score == 40.0

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
        from axm_audit.models.results import AuditResult

        def make_result(score: float) -> AuditResult:
            # Provide all 8 categories so score = input score
            return AuditResult(
                checks=[
                    self._make_check("QUALITY_LINT", score),
                    self._make_check("QUALITY_TYPE", score),
                    self._make_check("QUALITY_COMPLEXITY", score),
                    self._make_check("QUALITY_SECURITY", score),
                    self._make_check("DEPS_AUDIT", score),
                    self._make_check("DEPS_HYGIENE", score),
                    self._make_check("QUALITY_COVERAGE", score),
                    self._make_check("ARCH_COUPLING", score),
                    self._make_check("PRACTICE_DOCSTRING", score),
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


class TestDeadCodeRule:
    """Tests for DeadCodeRule (axm-ast dead-code integration)."""

    @pytest.fixture
    def rule(self) -> DeadCodeRule:
        """Return a DeadCodeRule instance."""
        from axm_audit.core.rules.dead_code import DeadCodeRule

        return DeadCodeRule()

    def test_dead_code_rule_id_format(self, rule: DeadCodeRule) -> None:
        """Rule ID should be QUALITY_DEAD_CODE."""
        assert rule.rule_id == "QUALITY_DEAD_CODE"

    def test_dead_code_success(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 90/100 and passed=False for 2 dead symbols."""
        import json

        from axm_audit.models.results import Severity

        mocker.patch("subprocess.run")  # Mock the axm-ast verification check

        # Mock the run_in_project call
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.run_in_project")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(
            [
                {"name": "foo", "module_path": "a.py", "line": 10, "kind": "function"},
                {"name": "bar", "module_path": "b.py", "line": 20, "kind": "class"},
            ]
        )
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 90.0  # 100 - (2 * 5)
        assert result.severity == Severity.WARNING
        assert result.details["dead_count"] == 2
        assert len(result.details["symbols"]) == 2
        assert len(result.details["top_offenders"]) == 2

    def test_dead_code_perfect(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 100/100 and passed=True for 0 dead symbols."""
        from axm_audit.models.results import Severity

        mocker.patch("subprocess.run")

        mock_run = mocker.patch("axm_audit.core.rules.dead_code.run_in_project")
        mock_result = mocker.Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.passed
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert result.details["dead_count"] == 0
        assert result.details["symbols"] == []

    def test_dead_code_skipped_not_available(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should skip gracefully if axm-ast is not available."""
        from axm_audit.models.results import Severity

        # Cause subprocess.run to raise an error
        mocker.patch(
            "subprocess.run", side_effect=FileNotFoundError("Mocked not found")
        )

        result = rule.check(tmp_path)

        assert result.passed  # Graceful skip shouldn't fail the build
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert "skipped" in result.details
        assert result.details["skipped"] is True
        assert "axm-ast is not available" in result.message

    def test_dead_code_json_decode_error(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should handle JSON parsing errors gracefully."""
        from axm_audit.models.results import Severity

        mocker.patch("subprocess.run")

        mock_run = mocker.patch("axm_audit.core.rules.dead_code.run_in_project")
        mock_result = mocker.Mock()
        mock_result.stdout = "Not a JSON output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 0.0
        assert result.severity == Severity.ERROR
        assert "parse" in result.message.lower()

    """Tests for DiffSizeRule (git diff --stat)."""

    def test_pass_small_diff(self, tmp_path: Path) -> None:
        """Small diff (< 200 lines) should pass with score 100."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality import DiffSizeRule

        # Mock git rev-parse succeeds
        rev_parse = MagicMock(returncode=0)
        # Mock git diff --stat with 50 lines changed
        diff_stat = MagicMock(
            returncode=0,
            stdout=" 3 files changed, 30 insertions(+), 20 deletions(-)\n",
        )

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["lines_changed"] == 50
        assert result.details["score"] == 100

    def test_fail_large_diff(self, tmp_path: Path) -> None:
        """Large diff (600 lines) should fail with reduced score."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality import DiffSizeRule

        rev_parse = MagicMock(returncode=0)
        diff_stat = MagicMock(
            returncode=0,
            stdout=" 10 files changed, 400 insertions(+), 200 deletions(-)\n",
        )

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["lines_changed"] == 600
        assert result.details["score"] == 33
        assert result.fix_hint is not None

    def test_skip_not_git_repo(self, tmp_path: Path) -> None:
        """Non-git directory should skip gracefully."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality import DiffSizeRule

        rev_parse = MagicMock(returncode=128)

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=rev_parse),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert "not a git repo" in result.message

    def test_pass_no_changes(self, tmp_path: Path) -> None:
        """No uncommitted changes → pass with score 100."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality import DiffSizeRule

        rev_parse = MagicMock(returncode=0)
        diff_stat = MagicMock(returncode=0, stdout="")

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["lines_changed"] == 0
        assert result.details["score"] == 100

    def test_skip_git_not_installed(self, tmp_path: Path) -> None:
        """Missing git binary should skip gracefully."""
        from unittest.mock import patch

        from axm_audit.core.rules.quality import DiffSizeRule

        with patch("shutil.which", return_value=None):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert "git not installed" in result.message

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_DIFF_SIZE."""
        from axm_audit.core.rules.quality import DiffSizeRule

        rule = DiffSizeRule()
        assert rule.rule_id == "QUALITY_DIFF_SIZE"
