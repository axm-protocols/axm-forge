"""Tests for models.project — test mirror."""

from __future__ import annotations

import pytest

from axm_init.models.project import ProjectConfig, ProjectMetadata


class TestProjectModelsImport:
    """Smoke: project models are importable."""

    def test_import_project_config(self) -> None:
        """ProjectConfig is importable."""
        assert ProjectConfig is not None

    def test_import_project_metadata(self) -> None:
        """ProjectMetadata is importable."""
        assert ProjectMetadata is not None


# ── Validation edge cases ────────────────────────────────────────────────────


class TestProjectConfigValidation:
    """Cover models/project.py validation edges."""

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProjectConfig(name="")

    def test_whitespace_only_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ProjectConfig(name="   ")

    def test_name_with_spaces_is_normalized(self) -> None:
        """Spaces in name are replaced with hyphens."""
        config = ProjectConfig(name="  My Cool Project  ")
        assert config.name == "my-cool-project"
