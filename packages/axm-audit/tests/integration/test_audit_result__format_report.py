from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import LintingRule
from axm_audit.models import CheckResult

pytestmark = pytest.mark.integration


def _make_ruff_output(project_path: Path, count: int = 3) -> str:
    """Build fake ruff JSON output with *count* issues."""
    issues = [
        {
            "filename": str(project_path / "src" / "mod.py"),
            "location": {"row": 10 + i},
            "code": f"E50{i}",
            "message": f"Issue number {i}",
        }
        for i in range(count)
    ]
    return json.dumps(issues)


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    """Create a minimal project layout."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").touch()
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture()
def lint_result(project_path: Path, monkeypatch: pytest.MonkeyPatch) -> CheckResult:
    """Run LintingRule.check with mocked ruff returning 3 issues."""
    mock_run = MagicMock()
    mock_run.return_value.stdout = _make_ruff_output(project_path, count=3)
    monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
    rule = LintingRule()
    return rule.check(project_path)


class TestLintTextRelativePaths:
    def test_paths_are_relative(self, lint_result, project_path):
        """Paths in text are relative (no project_path prefix)."""
        abs_prefix = str(project_path)
        for line in lint_result.text.splitlines():
            assert abs_prefix not in line, f"Absolute path found: {line!r}"
        assert "src/mod.py" in lint_result.text


class TestFormatReportIndentation:
    def test_detail_lines_indented(self, lint_result):
        """Report output has indented detail lines (5-space prefix)."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult

        report = format_report(AuditResult(checks=[lint_result]))
        bullet_lines = [ln for ln in report.splitlines() if "•" in ln]
        assert bullet_lines, "expected at least one bullet detail line"
        for line in bullet_lines:
            assert line.startswith("     "), f"Missing 5-space indent: {line!r}"


class TestFormatReportAlignmentUnchanged:
    def test_visual_structure(self, lint_result):
        """Failures section maintains visual alignment."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult

        report = format_report(AuditResult(checks=[lint_result]))
        lines = report.splitlines()
        assert any("❌" in line for line in lines)
        assert any("Problem:" in line for line in lines)
        bullet_lines = [ln for ln in lines if "•" in ln]
        for bl in bullet_lines:
            assert bl.startswith("     "), f"Bullet not indented: {bl!r}"
