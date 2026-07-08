from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.witnesses.audit_quality import AuditQualityRule

MODULE = "axm_audit.witnesses.audit_quality"


@pytest.fixture()
def rule(tmp_path: Path) -> AuditQualityRule:
    """Minimal AuditQualityRule pointing at a real tmp directory."""
    return AuditQualityRule(
        categories=["lint", "testing"],
        working_dir=str(tmp_path),
        exclude_rules=[],
        extra_dirs=[],
    )


# --- Edge case: all categories raise exceptions ---


def test_all_categories_raise_returns_failure(
    rule: AuditQualityRule,
) -> None:
    """When every audit_project call raises, validate returns failure."""
    with patch(f"{MODULE}.audit_project", side_effect=RuntimeError("boom")):
        result = rule.validate("")

    assert result.passed is False
    assert result.feedback is not None
    assert "All audit categories failed" in result.feedback.what


# --- Edge case: empty exclude_rules leaves failed_items unchanged ---


def test_empty_exclude_rules_no_filtering(
    rule: AuditQualityRule,
) -> None:
    """With no exclude_rules, all failed items are preserved."""
    failed = [
        {"rule_id": "E501", "message": "line too long"},
        {"rule_id": "F841", "message": "unused var"},
    ]
    agent_output = {"failed": failed, "passed": []}

    with (
        patch(f"{MODULE}.audit_project") as mock_audit,
        patch(f"{MODULE}.format_agent", return_value=agent_output),
    ):
        mock_audit.return_value.checks = []
        result = rule.validate("")

    assert result.passed is False
    assert result.metadata["audit"]["failed"] == failed
    assert result.feedback is not None
    assert "2 violation" in result.feedback.what


# --- Edge case: all failures excluded returns success ---


def test_all_failures_excluded_returns_success(tmp_path: Path) -> None:
    """When every failed rule matches an exclude prefix, validate succeeds."""
    rule = AuditQualityRule(
        categories=["lint"],
        working_dir=str(tmp_path),
        exclude_rules=["E5", "F8"],
        extra_dirs=[],
    )
    failed = [
        {"rule_id": "E501", "message": "line too long"},
        {"rule_id": "F841", "message": "unused var"},
    ]
    agent_output = {"failed": failed, "passed": []}

    with (
        patch(f"{MODULE}.audit_project") as mock_audit,
        patch(f"{MODULE}.format_agent", return_value=agent_output),
    ):
        mock_audit.return_value.checks = []
        result = rule.validate("")

    assert result.passed is True
    assert result.metadata["audit"]["failed"] == []


# --- False-green guard: a valid category outside the old witness whitelist
#     must actually be AUDITED (not silently swallowed to success) ---


def test_formerly_swallowed_category_actually_audits(tmp_path: Path) -> None:
    """``architecture`` is valid to the auditor but was absent from the old
    witness 5-category whitelist, so it used to be filtered to an empty set
    and short-circuit to ``WitnessResult.success()`` — a gate passing green
    having audited nothing. It must now run the category for real: the
    resulting metadata carries the auditor's output.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text('"""Pkg."""\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
    )
    rule = AuditQualityRule(
        categories=["architecture"],
        working_dir=str(tmp_path),
    )

    result = rule.validate("")

    assert result.metadata is not None
    assert "audit" in result.metadata, "witness swallowed the category (false-green)"


# --- False-green guard: unknown / empty categories are a hard RED config
#     error (the witness used to silently swallow them and pass green) ---


def test_truly_unknown_category_fails_loud(tmp_path: Path) -> None:
    """A category the auditor does not know returns failure, not success.

    Touches the real filesystem (``is_dir`` on ``tmp_path``), hence
    integration; the config-error branch itself runs no audit.
    """
    rule = AuditQualityRule(
        categories=["bogus_category"],
        working_dir=str(tmp_path),
    )
    result = rule.validate("")

    assert result.passed is False
    assert result.feedback is not None
    assert "Unknown audit category" in result.feedback.what
    assert "bogus_category" in result.feedback.what


def test_empty_categories_fails_loud(tmp_path: Path) -> None:
    """No categories configured is a config error — RED, not green."""
    rule = AuditQualityRule(
        categories=[],
        working_dir=str(tmp_path),
    )
    result = rule.validate("")

    assert result.passed is False
    assert result.feedback is not None
    assert "No audit categories" in result.feedback.what
