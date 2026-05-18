"""Split from ``test_audit_project_pipeline.py``."""


def test_rule_exception_doesnt_crash_others(tmp_path, mocker):
    """One rule raising should not prevent others from completing."""
    from axm_audit.core.auditor import audit_project
    from axm_audit.core.rules.quality import LintingRule

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    # Make LintingRule crash
    mocker.patch.object(LintingRule, "check", side_effect=RuntimeError("boom"))

    result = audit_project(tmp_path, category="lint")
    # Other lint rules still ran (FormattingRule, DiffSizeRule, DeadCodeRule)
    assert result.total >= 2

    # The broken rule is marked as failed with crash message
    lint_checks = [c for c in result.checks if c.rule_id == "QUALITY_LINT"]
    assert len(lint_checks) == 1
    assert not lint_checks[0].passed
    assert "crashed" in lint_checks[0].message.lower()

    # Traceback enrichment (AXM-198)
    details = lint_checks[0].details
    assert details is not None
    assert "traceback" in details
    assert "boom" in details["traceback"]


def test_traceback_truncated_500(tmp_path, mocker):
    """Traceback in details is truncated to last 500 characters."""
    from axm_audit.core.auditor import audit_project
    from axm_audit.core.rules.quality import LintingRule

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    # Make LintingRule crash with a very long exception message
    long_msg = "x" * 1000
    mocker.patch.object(LintingRule, "check", side_effect=RuntimeError(long_msg))

    result = audit_project(tmp_path, category="lint")
    lint_checks = [c for c in result.checks if c.rule_id == "QUALITY_LINT"]
    assert len(lint_checks) == 1
    details = lint_checks[0].details
    assert details is not None
    assert len(details["traceback"]) <= 500
