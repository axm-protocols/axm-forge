from __future__ import annotations

from pathlib import Path

from axm_audit.formatters import format_agent, format_report
from axm_audit.models.results import AuditResult, CheckResult, Severity

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_check_result_text_field() -> None:
    """CheckResult accepts and stores a `text` field."""
    cr = CheckResult(rule_id="X", passed=False, message="m", text="detail")
    assert cr.text == "detail"


def test_check_result_text_none_default() -> None:
    """CheckResult.text defaults to None when omitted."""
    cr = CheckResult(rule_id="X", passed=True, message="m")
    assert cr.text is None


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_failed_rules_produce_text(tmp_path: Path) -> None:
    """audit_project(category='lint') on a dirty project fills text on failures."""
    from axm_audit.core.auditor import audit_project

    # Create a minimal Python project with a lint violation
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text("import os\nimport sys\n")  # unused imports
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1.0"\n[tool.ruff]\nselect = ["F"]\n'
    )

    result = audit_project(tmp_path, category="lint")

    failed = [c for c in result.checks if not c.passed]
    assert failed, "Expected at least one failed check for lint violations"
    for c in failed:
        assert c.text is not None, f"{c.rule_id} failed but text is None"


def test_format_agent_uses_text() -> None:
    """format_agent() output contains the text from checks."""
    checks = [
        CheckResult(
            rule_id="QUALITY_LINT",
            passed=False,
            message="3 issues",
            text="    \u2022 [F401] foo.py:1: unused import",
            details={"score": 70, "issues": []},
        ),
    ]
    audit = AuditResult(
        checks=checks,
        quality_score=70.0,
        grade="C",
        project_path="/tmp/fake",
    )

    out = format_agent(audit)
    failed_entries = out["failed"]
    assert len(failed_entries) == 1
    assert failed_entries[0]["text"] == "    \u2022 [F401] foo.py:1: unused import"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_passed_rule_text_none_fallback_message() -> None:
    """Passed rule with text=None: format_agent falls back on message."""
    checks = [
        CheckResult(
            rule_id="QUALITY_LINT",
            passed=True,
            message="All clear",
            details={"score": 100},
        ),
    ]
    audit = AuditResult(
        checks=checks,
        quality_score=100.0,
        grade="A",
        project_path="/tmp/fake",
    )

    out = format_agent(audit)
    # Passed checks still render with message
    assert any("All clear" in str(p) for p in out["passed"])


def test_no_details_no_text_no_crash() -> None:
    """Rule with details=None and text=None renders gracefully."""
    checks = [
        CheckResult(
            rule_id="STRUCT_FILE",
            passed=False,
            message="Missing src/",
            severity=Severity.ERROR,
            details=None,
            text=None,
        ),
    ]
    audit = AuditResult(
        checks=checks,
        quality_score=0.0,
        grade="F",
        project_path="/tmp/fake",
    )

    # Neither formatter should crash
    agent_out = format_agent(audit)
    assert len(agent_out["failed"]) == 1

    report_out = format_report(audit)
    assert isinstance(report_out, str)
    assert "Missing src/" in report_out
