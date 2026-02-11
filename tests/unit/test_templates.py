"""Tests for template module — simplified single-template API."""

from pathlib import Path

from axm_init.core.templates import TemplateInfo, get_template_path


class TestGetTemplatePath:
    """Tests for get_template_path()."""

    def test_returns_path(self) -> None:
        """get_template_path() returns a Path object."""
        result = get_template_path()
        assert isinstance(result, Path)

    def test_path_exists(self) -> None:
        """Returned path points to an existing directory."""
        result = get_template_path()
        assert result.exists()
        assert result.is_dir()

    def test_path_is_python_project(self) -> None:
        """Returned path is the python-project template."""
        result = get_template_path()
        assert result.name == "python-project"


class TestTemplateInfo:
    """TemplateInfo model is still usable."""

    def test_template_info_creation(self, tmp_path: Path) -> None:
        """TemplateInfo can be instantiated."""
        info = TemplateInfo(
            name="python",
            description="A python project",
            path=tmp_path,
        )
        assert info.name == "python"
        assert info.path == tmp_path
