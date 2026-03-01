"""Tests for models.project — test mirror."""

from __future__ import annotations


class TestProjectModelsImport:
    """Smoke: project models are importable."""

    def test_import_project_config(self) -> None:
        """ProjectConfig is importable."""
        from axm_init.models.project import ProjectConfig

        assert ProjectConfig is not None

    def test_import_project_metadata(self) -> None:
        """ProjectMetadata is importable."""
        from axm_init.models.project import ProjectMetadata

        assert ProjectMetadata is not None
