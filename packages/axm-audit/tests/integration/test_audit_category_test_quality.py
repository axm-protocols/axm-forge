from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project


@pytest.mark.integration
def test_audit_project_category_test_quality_empty_returns_valid_result(
    tmp_path: Path,
) -> None:
    """audit_project accepts category='test_quality' and returns an AuditResult."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")

    result = audit_project(tmp_path, category="test_quality")

    assert result is not None
    assert result.project_path == str(tmp_path)


@pytest.mark.integration
def test_audit_project_with_dummy_rule_returns_1_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rule registered under test_quality produces at least one check."""
    from axm_audit.core import auditor as auditor_module
    from axm_audit.core.rules.quality import LintingRule

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")

    fake_registry = {"test_quality": [LintingRule]}
    monkeypatch.setattr(auditor_module, "get_registry", lambda: fake_registry)

    result = audit_project(tmp_path, category="test_quality")

    assert len(result.checks) >= 1


@pytest.mark.integration
def test_quality_check_hook_iterates_registry_not_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QualityCheckHook calls audit_project for test_quality (no allowlist skip)."""
    from axm_audit.hooks import quality_check as qc_module
    from axm_audit.hooks.quality_check import QualityCheckHook
    from axm_audit.models.results import AuditResult

    called_categories: list[str] = []

    def spy_audit(path: Path, category: str | None = None) -> AuditResult:
        called_categories.append(category or "")
        return AuditResult(project_path=str(path), checks=[])

    monkeypatch.setattr(qc_module, "audit_project", spy_audit)

    hook = QualityCheckHook()
    hook.execute(
        context={"working_dir": str(tmp_path)},
        categories=["test_quality"],
    )

    assert "test_quality" in called_categories
