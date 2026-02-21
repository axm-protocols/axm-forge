"""Tests for FormattingRule (ruff format --check)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

_PATCH = "axm_audit.core.rules.quality.run_in_project"


class TestFormattingRule:
    """Tests for FormattingRule (ruff format --check)."""

    def test_formatted_project_scores_100(self, tmp_path: Path) -> None:
        """Well-formatted project scores 100."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text('"""Module."""\n\nx = 1\n')

        # Mock ruff format --check returning clean output (exit 0, no files)
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100
        assert result.details["unformatted_count"] == 0

    def test_unformatted_project_reduces_score(self, tmp_path: Path) -> None:
        """Unformatted files reduce score."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x=1\n")

        # Mock ruff format --check returning 3 unformatted files
        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="src/a.py\nsrc/b.py\nsrc/c.py\n",
            stderr="",
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.passed is True  # score 85 >= 80
        assert result.details is not None
        assert result.details["unformatted_count"] == 3
        assert result.details["score"] == 85

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_FORMAT."""
        from axm_audit.core.rules.quality import FormattingRule

        assert FormattingRule().rule_id == "QUALITY_FORMAT"

    def test_fix_hint_when_violations(self, tmp_path: Path) -> None:
        """Fix hint present when there are unformatted files."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x=1\n")

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="src/mod.py\n", stderr=""
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.fix_hint is not None
        assert "ruff format" in result.fix_hint

    def test_no_fix_hint_when_clean(self, tmp_path: Path) -> None:
        """No fix hint when all files are properly formatted."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.fix_hint is None

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """Missing src/ directory returns failure."""
        from axm_audit.core.rules.quality import FormattingRule

        rule = FormattingRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "src/ directory not found" in result.message

    def test_includes_tests_directory(self, tmp_path: Path) -> None:
        """Both src/ and tests/ are checked when both exist."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()
        tests = tmp_path / "tests"
        tests.mkdir()

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["checked"] == "src/ tests/"

    def test_many_unformatted_capped_at_20(self, tmp_path: Path) -> None:
        """Unformatted files list is capped at 20."""
        from axm_audit.core.rules.quality import FormattingRule

        src = tmp_path / "src"
        src.mkdir()

        # Generate 30 unformatted files in output
        files = "\n".join(f"src/file_{i}.py" for i in range(30))
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=files + "\n", stderr=""
        )
        with patch(_PATCH, return_value=mock_result):
            rule = FormattingRule()
            result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["unformatted_count"] == 30
        assert len(result.details["unformatted_files"]) == 20  # capped


class TestFormattingRuleIntegration:
    """Functional tests for FormattingRule via audit_project."""

    def test_audit_includes_format_rule(self, tmp_path: Path) -> None:
        """audit_project with quality category includes QUALITY_FORMAT."""
        from axm_audit.core.auditor import audit_project

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package."""\n')
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
        )

        result = audit_project(tmp_path, category="quality")
        rule_ids = [c.rule_id for c in result.checks]
        assert "QUALITY_FORMAT" in rule_ids
