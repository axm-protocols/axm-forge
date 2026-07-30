"""Split from ``test_helpers.py``."""

from pathlib import Path


def test_cache_cleared_between_audits(tmp_path: Path) -> None:
    """Two sequential audit_project() calls → second gets fresh cache."""
    from axm_audit.core.rules._helpers import get_ast_cache

    # Minimal project
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'pkg'\n")

    from axm_audit.core.auditor import audit_project

    audit_project(tmp_path)
    assert get_ast_cache() is None  # cleaned up after first run

    audit_project(tmp_path)
    assert get_ast_cache() is None  # cleaned up after second run
