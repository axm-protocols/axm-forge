"""Split from ``test_toml_loader_with_workspace_fallback.py``."""

from pathlib import Path

import pytest

from axm_init.checks._utils import load_toml


class TestLoadToml:
    """Tests for load_toml()."""

    def test_load_toml_valid(self, tmp_path: Path) -> None:
        """Valid pyproject.toml is parsed correctly."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n')
        data = load_toml(tmp_path)
        assert data is not None
        assert data["project"]["name"] == "test-pkg"

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(None, id="missing"),
            pytest.param("{{invalid toml}}", id="corrupt"),
        ],
    )
    def test_load_toml_returns_none(self, tmp_path: Path, content: str | None) -> None:
        """Missing or corrupt pyproject.toml returns None."""
        if content is not None:
            (tmp_path / "pyproject.toml").write_text(content)
        data = load_toml(tmp_path)
        assert data is None

    def test_shipped_manifest_declares_no_console_script(self) -> None:
        """AC1: the shipped manifest exposes neither legacy CLI entry point."""
        package_root = Path(__file__).resolve().parents[2]

        data = load_toml(package_root)

        assert data is not None
        project = data["project"]
        assert isinstance(project, dict)
        entry_points = project.get("entry-points", {})
        assert "scripts" not in project
        assert isinstance(entry_points, dict)
        assert "axm.commands" not in entry_points

    def test_shipped_manifest_declares_no_axm_commands_group(self) -> None:
        """AC1: the shipped manifest has no ``axm.commands`` entry-point group."""
        package_root = Path(__file__).resolve().parents[2]

        data = load_toml(package_root)

        assert data is not None
        project = data["project"]
        assert isinstance(project, dict)
        entry_points = project.get("entry-points", {})
        assert isinstance(entry_points, dict)
        assert "axm.commands" not in entry_points
