"""Split from ``test_audit_category_test_quality.py``."""

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project


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
