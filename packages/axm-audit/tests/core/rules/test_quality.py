"""Tests for Quality Rules — LintingRule, TypeCheckRule, DiffSizeRule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

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


class TestTypeCheckVenvAlignment:
    """Tests for AXM-796: gate mypy env must match pre-commit hooks."""

    def test_type_check_uses_project_venv(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """TypeCheckRule must NOT inject mypy via --with when project has a venv.

        Pre-commit hooks run mypy from the project's own venv, so the gate
        must do the same to see identical type errors and honour the same
        type-stub availability.
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text("def greet(name: str) -> str:\n    return name\n")

        # Simulate a project venv with mypy already installed
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Patch run_in_project to capture the call
        mock_run = mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        rule.check(tmp_path)

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        # Gate must NOT inject mypy — it should use the project's own copy
        with_pkgs = kwargs.get("with_packages") or []
        assert "mypy" not in with_pkgs, (
            "TypeCheckRule must use the project venv's mypy, "
            "not inject via --with; got with_packages={with_pkgs!r}"
        )

    def test_no_unused_ignore_contradiction(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """A `# type: ignore` accepted by pre-commit must not become
        an 'unused-ignore' error in the gate.

        When the gate uses the same venv as pre-commit, mypy sees
        identical missing-stub / import errors, so a valid type-ignore
        comment stays valid.  This test verifies the gate passes when
        mypy reports zero errors (i.e. the ignore suppressed a real error).
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # File with type: ignore that suppresses a real import error
        (src / "client.py").write_text(
            "import somelib  # type: ignore[import-untyped]\n\n"
            "def call() -> str:\n"
            "    return somelib.run()\n"
        )

        # Simulate project venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Simulate mypy output: zero errors (type: ignore suppressed the
        # real error, just like pre-commit would see).  If the gate used
        # a different env, mypy might report "unused-ignore" instead.
        mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["error_count"] == 0, (
            "Gate must not produce unused-ignore errors for comments "
            "that pre-commit accepts"
        )


class TestTypeCheckRule:
    """Tests for TypeCheckRule (mypy integration)."""

    def test_typed_project_high_score(self, tmp_path: Path) -> None:
        """Fully typed project should score 100 and pass."""
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
        assert result.passed is True
        assert result.details["score"] == 100

    def test_type_errors_reduce_score(self, tmp_path: Path) -> None:
        """Type errors should fail with zero tolerance."""
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
        assert result.passed is False

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

    def test_type_check_zero_errors_passes(self, tmp_path: Path) -> None:
        """Zero mypy errors → passed=True, score=100."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "clean.py").write_text("def double(x: int) -> int:\n    return x * 2\n")

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100

    def test_type_check_one_error_fails(self, tmp_path: Path) -> None:
        """One mypy error → passed=False (zero tolerance)."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["error_count"] == 1

    def test_type_check_two_errors_fails(self, tmp_path: Path) -> None:
        """Two mypy errors → passed=False (zero tolerance)."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n\n'
            'def sub(a: int, b: int) -> int:\n    return "also wrong"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["error_count"] == 2

    def test_lint_threshold_unchanged(self, tmp_path: Path) -> None:
        """Lint rule still uses score threshold — no regression from type fix."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package."""\n')
        # Single unused import → small score reduction, still above threshold
        (src / "mild.py").write_text('"""Mild issue."""\nimport os\n')

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        # Lint uses scoring threshold, not zero-tolerance
        assert result.details["issue_count"] > 0
        assert result.details["score"] >= 90


class TestAuditResultScoring:
    """Tests for AuditResult quality_score and grade (8-category model)."""

    def _make_check(self, rule_id: str, score: float) -> CheckResult:
        """Helper to create a CheckResult with a score and category."""
        from _registry_helpers import build_rule_category_map

        from axm_audit.models.results import CheckResult

        category_map = build_rule_category_map()
        return CheckResult(
            rule_id=rule_id,
            passed=True,
            message="",
            details={"score": score},
            category=category_map.get(rule_id),
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
        """quality_score with only lint/type/complexity → normalized partial score."""
        from axm_audit.models.results import AuditResult

        result = AuditResult(
            checks=[
                self._make_check("QUALITY_LINT", 80),  # 80 * 0.20 = 16
                self._make_check("QUALITY_TYPE", 60),  # 60 * 0.15 = 9
                self._make_check("QUALITY_COMPLEXITY", 100),  # 100 * 0.15 = 15
            ]
        )
        # 3 categories present, weight_sum = 0.20 + 0.15 + 0.15 = 0.50
        # Normalized: (16 + 9 + 15) / 0.50 = 80.0
        assert result.quality_score == 80.0

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
        """Large diff (1100 lines) should fail with reduced score."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality import DiffSizeRule

        rev_parse = MagicMock(returncode=0)
        diff_stat = MagicMock(
            returncode=0,
            stdout=" 20 files changed, 700 insertions(+), 400 deletions(-)\n",
        )

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["lines_changed"] == 1100
        assert result.details["score"] == 12
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

    # -- _compute_score with new defaults --

    def test_compute_score_new_defaults(self) -> None:
        """300 lines is under new ideal (400) → score 100."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule._compute_score(300) == 100

    def test_compute_score_boundary(self) -> None:
        """Exactly at ideal (400) → score 100."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule._compute_score(400) == 100

    def test_compute_score_midrange(self) -> None:
        """800 lines → 50 (midpoint of [400, 1200])."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule._compute_score(800) == 50

    def test_compute_score_over_max(self) -> None:
        """1200 lines (at max) → score 0."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule._compute_score(1200) == 0

    # -- Config-reading tests --

    def test_config_override_ideal(self, tmp_path: Path) -> None:
        """pyproject.toml with diff_size_ideal=300 → rule uses 300."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = 300\n"
        )
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 300
        assert max_lines == 1200  # default

    def test_config_override_max(self, tmp_path: Path) -> None:
        """pyproject.toml with diff_size_max=1000 → rule uses 1000."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_max = 1000\n"
        )
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 400  # default
        assert max_lines == 1000

    def test_no_config_uses_defaults(self, tmp_path: Path) -> None:
        """pyproject.toml without [tool.axm-audit] → defaults."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_partial_config(self, tmp_path: Path) -> None:
        """Only diff_size_ideal set → diff_size_max uses default."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = 250\n"
        )
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 250
        assert max_lines == 1200

    def test_invalid_config_value(self, tmp_path: Path) -> None:
        """Non-numeric diff_size_ideal → falls back to default."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            '[tool.axm-audit]\ndiff_size_ideal = "abc"\n'
        )
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_negative_threshold(self, tmp_path: Path) -> None:
        """Negative diff_size_ideal → falls back to default."""
        from axm_audit.core.rules.quality import _read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = -10\n"
        )
        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_missing_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml at all → defaults apply."""
        from axm_audit.core.rules.quality import _read_diff_config

        ideal, max_lines = _read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200


class TestParseMypyErrors:
    """Tests for _parse_mypy_errors — non-dict JSON handling.

    Ref: AXM-1220.
    """

    def test_parse_mypy_errors_string_json(self) -> None:
        """String JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = '"some status string"\n'
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_list_json(self) -> None:
        """List JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = '["a", "b"]\n'
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_valid_error(self) -> None:
        """Valid mypy error JSON dict should be parsed correctly."""
        import json

        from axm_audit.core.rules.quality import TypeCheckRule

        entry = {
            "severity": "error",
            "file": "src/main.py",
            "line": 10,
            "message": "Incompatible return type",
            "code": "return-value",
        }
        stdout = json.dumps(entry) + "\n"
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 1
        assert len(errors) == 1
        assert errors[0]["file"] == "src/main.py"
        assert errors[0]["line"] == 10
        assert errors[0]["message"] == "Incompatible return type"
        assert errors[0]["code"] == "return-value"

    def test_parse_mypy_errors_mixed(self) -> None:
        """Mixed stdout: skips string line, parses valid error."""
        import json

        from axm_audit.core.rules.quality import TypeCheckRule

        error_entry = {
            "severity": "error",
            "file": "src/bad.py",
            "line": 5,
            "message": "Type mismatch",
            "code": "assignment",
        }
        stdout = '"some status string"\n' + json.dumps(error_entry) + "\n"
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 1
        assert len(errors) == 1
        assert errors[0]["file"] == "src/bad.py"

    def test_parse_mypy_errors_empty_stdout(self) -> None:
        """Empty stdout returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        count, errors = TypeCheckRule._parse_mypy_errors("")
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_integer_json(self) -> None:
        """Integer JSON line should be skipped."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = "42\n"
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_null_json(self) -> None:
        """Null JSON line should be skipped."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = "null\n"
        count, errors = TypeCheckRule._parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []


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
