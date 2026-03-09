"""Tests for checks/_utils.py — shared TOML loading utility."""

from __future__ import annotations

from pathlib import Path


class TestLoadToml:
    """Tests for _load_toml()."""

    def test_load_toml_valid(self, tmp_path: Path) -> None:
        """Valid pyproject.toml is parsed correctly."""
        from axm_init.checks._utils import _load_toml

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n')
        data = _load_toml(tmp_path)
        assert data is not None
        assert data["project"]["name"] == "test-pkg"

    def test_load_toml_missing(self, tmp_path: Path) -> None:
        """Missing pyproject.toml returns None."""
        from axm_init.checks._utils import _load_toml

        data = _load_toml(tmp_path)
        assert data is None

    def test_load_toml_corrupt(self, tmp_path: Path) -> None:
        """Corrupt TOML returns None."""
        from axm_init.checks._utils import _load_toml

        (tmp_path / "pyproject.toml").write_text("{{invalid toml}}")
        data = _load_toml(tmp_path)
        assert data is None
