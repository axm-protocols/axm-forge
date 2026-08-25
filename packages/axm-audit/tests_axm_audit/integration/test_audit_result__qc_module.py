from __future__ import annotations

from pathlib import Path

import pytest


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
