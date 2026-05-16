"""Split from ``test_workspace_checks.py``."""


def test_workspace_category_discovered() -> None:
    """workspace category exists in ALL_CHECKS."""
    from axm_init.core.checker import ALL_CHECKS

    assert "workspace" in ALL_CHECKS
    assert len(ALL_CHECKS["workspace"]) == 9
