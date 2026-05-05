"""Unit tests for axm_audit.core.rules.quality (no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest


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
