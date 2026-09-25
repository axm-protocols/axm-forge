"""Split from ``test_scaffold_template_rendering.py``."""

from axm_init.core.templates import get_template_path


class TestGetTemplatePathIntegration:
    """Tests for get_template_path() — filesystem-touching scope."""

    def test_path_exists(self) -> None:
        """Returned path points to an existing directory."""
        result = get_template_path()
        assert result.exists()
        assert result.is_dir()


def test_standalone_is_default() -> None:
    path = get_template_path()
    assert path.name == "python-project"
    assert path.is_dir()
