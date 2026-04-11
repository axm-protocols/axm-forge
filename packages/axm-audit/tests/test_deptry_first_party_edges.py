from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.dependencies import (
    _detect_first_party_packages,
    _has_deptry_config,
)


class TestHasDeptryConfig:
    """Tests for the extracted _has_deptry_config helper."""

    def test_returns_true_when_known_first_party_set(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.deptry]\nknown_first_party = ["mypkg"]\n')
        assert _has_deptry_config(tmp_path) is True

    def test_returns_false_when_no_deptry_section(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'foo'\n")
        assert _has_deptry_config(tmp_path) is False

    def test_returns_false_when_no_pyproject(self, tmp_path: Path) -> None:
        assert _has_deptry_config(tmp_path) is False

    def test_returns_false_on_malformed_toml(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[[invalid toml content")
        assert _has_deptry_config(tmp_path) is False


class TestDetectFirstPartyEdgeCases:
    """Edge-case tests for _detect_first_party_packages."""

    def test_malformed_pyproject_falls_through_to_scan(self, tmp_path: Path) -> None:
        """Malformed pyproject.toml logs debug and falls through to dir scan."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[[invalid toml")
        src = tmp_path / "src"
        src.mkdir()
        (src / "mypkg").mkdir()
        (src / "mypkg" / "__init__.py").touch()
        assert _detect_first_party_packages(tmp_path) == ["mypkg"]

    def test_empty_src_directory(self, tmp_path: Path) -> None:
        """Empty src/ directory returns empty list."""
        (tmp_path / "src").mkdir()
        assert _detect_first_party_packages(tmp_path) == []

    def test_deptry_config_short_circuits(self, tmp_path: Path) -> None:
        """When known_first_party is already configured, return [] immediately."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.deptry]\nknown_first_party = ["existing"]\n')
        src = tmp_path / "src"
        src.mkdir()
        (src / "mypkg").mkdir()
        (src / "mypkg" / "__init__.py").touch()
        assert _detect_first_party_packages(tmp_path) == []
