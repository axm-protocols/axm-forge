"""Tests for template catalog."""

import pytest

from axm_init.core.templates import TemplateType, get_template_catalog, resolve_template


class TestTemplateCatalog:
    """Tests for template catalog functions."""

    def test_get_catalog_returns_dict(self) -> None:
        """Test catalog returns dictionary of templates."""
        catalog = get_template_catalog()
        assert isinstance(catalog, dict)
        assert TemplateType.PYTHON in catalog

    def test_python_template_has_required_fields(self) -> None:
        """Test Python template has name, description, path."""
        catalog = get_template_catalog()
        python_template = catalog[TemplateType.PYTHON]

        assert python_template.name == "python"
        assert "Python" in python_template.description
        assert python_template.path is not None


class TestResolveTemplate:
    """Tests for resolve_template function."""

    def test_resolve_python_template(self) -> None:
        """Test resolving 'python' template."""
        template = resolve_template("python")
        assert template.name == "python"

    def test_resolve_unknown_template_raises(self) -> None:
        """Test resolving unknown template raises ValueError."""
        with pytest.raises(ValueError, match="Unknown template"):
            resolve_template("nonexistent")

    def test_error_message_lists_available(self) -> None:
        """Test error message lists available templates."""
        with pytest.raises(ValueError, match="python"):
            resolve_template("invalid")
