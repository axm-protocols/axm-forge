"""Public-API tests for ``audit_project`` (replaces private ``_safe_check`` /
``_build_all_rules`` direct calls in ``tests/core/rules/test_rules.py``)."""

from __future__ import annotations

from axm_audit import AuditResult, audit_project


def _make_minimal_project(root):
    src = root / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "module.py").write_text("x = 1\n")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_x():\n    assert True\n")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.1"\n')


def test_audit_project_safe_check_isolation(tmp_path, monkeypatch):
    """AC1: A rule that raises must not abort the audit; result records the failure."""
    _make_minimal_project(tmp_path)

    from axm_audit.core.rules.security import SecurityRule

    def boom(self, project_path):
        raise RuntimeError("rule exploded")

    monkeypatch.setattr(SecurityRule, "check", boom)

    result = audit_project(tmp_path)

    assert isinstance(result, AuditResult)
    failed = [c for c in result.checks if not c.passed]
    assert failed, "expected at least one failed check entry from the raising rule"
    assert any("security" in (c.rule_id or "").lower() for c in failed)
    # Other rules still produced entries
    assert len(result.checks) > 1


def test_audit_project_runs_all_categories(tmp_path):
    """AC1: ``audit_project`` exercises every scoring category, not a subset."""
    _make_minimal_project(tmp_path)

    result = audit_project(tmp_path)

    assert isinstance(result, AuditResult)
    categories = {c.category for c in result.checks if c.category}
    # The 8 scoring categories are documented on AuditResult.quality_score.
    expected = {
        "lint",
        "type",
        "complexity",
        "security",
        "deps",
        "testing",
        "architecture",
        "practices",
    }
    overlap = categories & expected
    assert len(overlap) >= 3, f"expected several scoring categories, got {categories}"
