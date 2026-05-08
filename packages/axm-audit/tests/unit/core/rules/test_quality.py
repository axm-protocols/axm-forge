"""Unit tests for axm_audit.core.rules.quality (no I/O)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import FormattingRule, LintingRule
from axm_audit.models import CheckResult


class TestDiffSizeRuleUnit:
    """Pure tests for DiffSizeRule (mocked subprocess, no real I/O)."""

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
        assert result.score == 100

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
        assert result.score == 12
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
        assert result.score == 100

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

    # -- compute_score with new defaults --

    def test_compute_score_new_defaults(self) -> None:
        """300 lines is under new ideal (400) → score 100."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule.compute_score(300) == 100

    def test_compute_score_boundary(self) -> None:
        """Exactly at ideal (400) → score 100."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule.compute_score(400) == 100

    def test_compute_score_midrange(self) -> None:
        """800 lines → 50 (midpoint of [400, 1200])."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule.compute_score(800) == 50

    def test_compute_score_over_max(self) -> None:
        """1200 lines (at max) → score 0."""
        from axm_audit.core.rules.quality import DiffSizeRule

        assert DiffSizeRule.compute_score(1200) == 0


class TestLintingRuleUnit:
    """Pure tests for LintingRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_LINT."""
        from axm_audit.core.rules.quality import LintingRule

        rule = LintingRule()
        assert rule.rule_id == "QUALITY_LINT"


class TestTypeCheckRuleUnit:
    """Pure tests for TypeCheckRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_TYPE."""
        from axm_audit.core.rules.quality import TypeCheckRule

        rule = TypeCheckRule()
        assert rule.rule_id == "QUALITY_TYPE"


class TestParseMypyErrors:
    """Tests for _parse_mypy_errors — non-dict JSON handling.

    Ref: AXM-1220.
    """

    def test_parse_mypy_errors_string_json(self) -> None:
        """String JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = '"some status string"\n'
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_list_json(self) -> None:
        """List JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        stdout = '["a", "b"]\n'
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
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
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
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
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 1
        assert len(errors) == 1
        assert errors[0]["file"] == "src/bad.py"

    def test_parse_mypy_errors_empty_stdout(self) -> None:
        """Empty stdout returns (0, [])."""
        from axm_audit.core.rules.quality import TypeCheckRule

        count, errors = TypeCheckRule.parse_mypy_errors("")
        assert count == 0
        assert errors == []

    @pytest.mark.parametrize(
        "stdout",
        [
            pytest.param("42\n", id="integer"),
            pytest.param("null\n", id="null"),
            pytest.param("true\n", id="boolean"),
            pytest.param('"plain string"\n', id="string"),
            pytest.param("[1, 2, 3]\n", id="array"),
        ],
    )
    def test_parse_mypy_errors_skips_non_dict_json(self, stdout: str) -> None:
        """Non-dict JSON scalars on a line should be skipped."""
        from axm_audit.core.rules.quality import TypeCheckRule

        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []


MODULE = "axm_audit.core.rules.quality"


@pytest.fixture()
def rule() -> FormattingRule:
    return FormattingRule()


@pytest.fixture()
def _bypass_early(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub check_src, _get_audit_targets, and run_in_project."""
    monkeypatch.setattr(f"{MODULE}.FormattingRule.check_src", lambda self, p: None)
    monkeypatch.setattr(
        f"{MODULE}._get_audit_targets",
        lambda p: (["src/"], "src/"),
    )
    monkeypatch.setattr(
        f"{MODULE}.run_in_project",
        lambda *a, **kw: MagicMock(stdout="", returncode=0),
    )


def _patch_unformatted(monkeypatch: pytest.MonkeyPatch, files: list[str]) -> None:
    monkeypatch.setattr(
        f"{MODULE}.FormattingRule._parse_unformatted_files",
        lambda self, result: files,
    )


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_bare_paths(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must contain bare file paths, no bullets, no padding."""
    _patch_unformatted(monkeypatch, ["src/a.py", "src/b.py", "src/c.py"])
    result = rule.check(Path("/fake"))
    assert result.text == "src/a.py\nsrc/b.py\nsrc/c.py"


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_none_on_pass(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must be None when no unformatted files."""
    _patch_unformatted(monkeypatch, [])
    result = rule.check(Path("/fake"))
    assert result.text is None


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_cap_at_20(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must contain at most 20 lines, no trailing newline."""
    files = [f"src/file_{i}.py" for i in range(30)]
    _patch_unformatted(monkeypatch, files)
    result = rule.check(Path("/fake"))
    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 20
    assert not result.text.endswith("\n")


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_single_file(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single unformatted file — no trailing newline."""
    _patch_unformatted(monkeypatch, ["src/only.py"])
    result = rule.check(Path("/fake"))
    assert result.text == "src/only.py"


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    """Create a minimal project layout."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").touch()
    (tmp_path / "tests").mkdir()
    return tmp_path


class TestPathOutsideProject:
    def test_short_path_fallback(self, project_path, monkeypatch):
        """File outside project_path keeps original path."""
        issues = [
            {
                "filename": "/other/place/file.py",
                "location": {"row": 1},
                "code": "E501",
                "message": "Line too long",
            }
        ]
        mock_run = MagicMock()
        mock_run.return_value.stdout = json.dumps(issues)
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is not None
        assert "/other/place/file.py" in result.text


class TestZeroIssuesPassed:
    def test_no_crash_text_none(self, project_path, monkeypatch):
        """Clean project: text=None, no crash."""
        mock_run = MagicMock()
        mock_run.return_value.stdout = "[]"
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is None
        assert result.passed is True


class TestTwentyIssuesCap:
    def test_capped_at_twenty(self, project_path, monkeypatch):
        """text has exactly 20 lines, details.issues has 20 entries."""
        issues = [
            {
                "filename": str(project_path / "src" / "mod.py"),
                "location": {"row": i},
                "code": "E501",
                "message": f"Issue {i}",
            }
            for i in range(25)
        ]
        mock_run = MagicMock()
        mock_run.return_value.stdout = json.dumps(issues)
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is not None
        assert result.details is not None
        assert len(result.text.splitlines()) == 20
        assert len(result.details["issues"]) == 20


class TestOtherRulesTextRendering:
    def test_format_check_details_adds_indent(self):
        """Rendered failure details from check.text are 5-space indented."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult, Severity

        check = CheckResult(
            rule_id="OTHER_RULE",
            passed=False,
            message="Some issue",
            severity=Severity.WARNING,
            details={},
            text="line one\nline two",
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     line one" in report
        assert "     line two" in report
