"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

from axm_git.core.runner import detect_package_name


class TestDetectPackageName:
    """Test detect_package_name helper."""

    def test_valid_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-pkg"\n')
        assert detect_package_name(tmp_path) == "my-pkg"

    def test_missing_pyproject(self, tmp_path: Path) -> None:
        assert detect_package_name(tmp_path) is None

    def test_no_project_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[build-system]\n")
        assert detect_package_name(tmp_path) is None

    def test_invalid_toml(self, tmp_path: Path) -> None:
        """Malformed TOML returns None via exception handler."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("{{invalid toml}}")
        assert detect_package_name(tmp_path) is None
