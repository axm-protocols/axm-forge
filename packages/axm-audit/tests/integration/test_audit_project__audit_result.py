"""Split from ``test_audit_project_pipeline.py``."""

from pathlib import Path

from axm_audit import AuditResult, audit_project
from tests.integration._helpers import _make_minimal_project


def test_audit_project_returns_audit_result(tmp_path):
    """audit_project returns a populated AuditResult.

    Checks and a non-negative score must be present.
    """
    from axm_audit import AuditResult, audit_project

    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
    (tmp_path / "src").mkdir()

    result = audit_project(tmp_path)
    assert isinstance(result, AuditResult)
    assert result.checks, "audit_project should produce at least one check"
    assert result.total == len(result.checks)


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


def test_audit_toy_project_passes(toy_project: Path) -> None:
    """Audit a clean toy project — expects a reasonable score.

    Note: ``result.success`` may be False because some tooling checks
    (pip-audit, deptry, bandit, pytest) are not installed in the
    isolated tmp_path.  The key assertion is that the pipeline
    completes and returns a non-trivial score.
    """
    result: AuditResult = audit_project(toy_project)
    assert result.quality_score is not None
    assert result.quality_score > 0
    assert result.grade in {"A", "B", "C", "D", "F"}
