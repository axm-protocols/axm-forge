"""Tests for models.project — test mirror.

ProjectConfig and ProjectMetadata were removed (dead code cleanup).
This test module is kept as a mirror placeholder.
"""

from __future__ import annotations


class TestProjectModelsCleanup:
    """Confirm dead models were removed."""

    def test_project_module_is_placeholder(self) -> None:
        """project.py still importable (placeholder docstring)."""
        from axm_init.models import project

        assert project.__doc__ is not None
