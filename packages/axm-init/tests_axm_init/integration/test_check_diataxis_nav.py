"""Split from ``test_diataxis_docs_layout_requirements.py``."""

from pathlib import Path

from axm_init.checks.docs import check_diataxis_nav


def test_diataxis_nav_workspace_fallback(workspace_member: Path) -> None:
    """Workspace member falls back to root mkdocs.yml for nav check."""
    result = check_diataxis_nav(workspace_member)
    assert result.passed is True
