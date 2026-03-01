"""Tests for Quality Rules — LintingRule, TypeCheckRule, DiffSizeRule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
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


class TestAuditResultScoring:
    """Tests for AuditResult quality_score and grade (8-category model)."""

    # Rule-id → scoring category mapping
    _RULE_CATEGORY: ClassVar[dict[str, str]] = {
        "QUALITY_LINT": "lint",
        "QUALITY_FORMAT": "lint",
        "QUALITY_DIFF_SIZE": "lint",
        "QUALITY_DEAD_CODE": "lint",
        "QUALITY_TYPE": "type",
        "QUALITY_COMPLEXITY": "complexity",
        "QUALITY_SECURITY": "security",
        "DEPS_AUDIT": "deps",
        "DEPS_HYGIENE": "deps",
        "QUALITY_COVERAGE": "testing",
        "ARCH_COUPLING": "architecture",
        "ARCH_CIRCULAR": "architecture",
        "ARCH_GOD_CLASS": "architecture",
        "ARCH_DUPLICATION": "architecture",
        "PRACTICE_DOCSTRING": "practices",
        "PRACTICE_BARE_EXCEPT": "practices",
        "PRACTICE_SECURITY": "practices",
        "PRACTICE_BLOCKING_IO": "practices",
        "PRACTICE_LOGGING": "practices",
        "PRACTICE_TEST_MIRROR": "practices",
    }

    def _make_check(self, rule_id: str, score: float) -> CheckResult:
        """Helper to create a CheckResult with a score and category."""
        from axm_audit.models.results import CheckResult

        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
            category=self._RULE_CATEGORY.get(rule_id),
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


class TestDiffSizeRule:
    """Tests for DiffSizeRule (git diff --stat)."""

    def test_pass_small_diff(self, tmp_path: Path) -> None:
        """Small diff (<200 lines) should pass with score 100."""
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


class TestGetAuditTargets:
    """Tests for _get_audit_targets() helper (AXM-203)."""

    def test_with_tests_dir(self, tmp_path: Path) -> None:
        """Return both src and tests when tests/ exists."""
        from axm_audit.core.rules.quality import _get_audit_targets

        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()

        targets, checked = _get_audit_targets(tmp_path)
        assert targets == [str(tmp_path / "src"), str(tmp_path / "tests")]
        assert checked == "src/ tests/"

    def test_without_tests_dir(self, tmp_path: Path) -> None:
        """Return only src when tests/ does not exist."""
        from axm_audit.core.rules.quality import _get_audit_targets

        (tmp_path / "src").mkdir()

        targets, checked = _get_audit_targets(tmp_path)
        assert targets == [str(tmp_path / "src")]
        assert checked == "src/"
