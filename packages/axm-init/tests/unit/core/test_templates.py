"""Unit-level tests for core/templates.py."""

from __future__ import annotations

from axm_init.core.templates import TemplateType, get_template_path


class TestGetTemplatePathUnit:
    """Tests for get_template_path() — pure value checks."""

    def test_path_is_python_project(self) -> None:
        """Returned path is the python-project template."""
        result = get_template_path()
        assert result.name == "python-project"


# --- TemplateType dispatch tests ---


class TestTemplateTypeUnit:
    """TemplateType + get_template_path dispatch — pure value checks."""

    def test_standalone_explicit(self) -> None:
        path = get_template_path(TemplateType.STANDALONE)
        assert path.name == "python-project"
