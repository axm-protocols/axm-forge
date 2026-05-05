from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.dependencies import detect_first_party_packages


class TestHasDeptryConfigViaDetect:
    """Test deptry-config detection through the public detect_first_party_packages.

    detect_first_party_packages short-circuits to [] when
    [tool.deptry] known_first_party is configured, so it transitively exercises
    the config-detection logic. We seed an src/ package so an empty result
    proves the config check fired (vs. a missing-package empty).
    """

    @staticmethod
    def _seed_src_pkg(tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "mypkg").mkdir()
        (src / "mypkg" / "__init__.py").touch()

    def test_short_circuits_when_known_first_party_set(self, tmp_path: Path) -> None:
        self._seed_src_pkg(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.deptry]\nknown_first_party = ["mypkg"]\n'
        )
        assert detect_first_party_packages(tmp_path) == []

    def test_does_not_short_circuit_without_deptry_section(
        self, tmp_path: Path
    ) -> None:
        self._seed_src_pkg(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        assert detect_first_party_packages(tmp_path) == ["mypkg"]

    def test_does_not_short_circuit_without_pyproject(self, tmp_path: Path) -> None:
        self._seed_src_pkg(tmp_path)
        assert detect_first_party_packages(tmp_path) == ["mypkg"]

    def test_does_not_short_circuit_on_malformed_toml(self, tmp_path: Path) -> None:
        self._seed_src_pkg(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[[invalid toml content")
        assert detect_first_party_packages(tmp_path) == ["mypkg"]


class TestDetectFirstPartyEdgeCases:
    """Edge-case tests for detect_first_party_packages."""

    def test_malformed_pyproject_falls_through_to_scan(self, tmp_path: Path) -> None:
        """Malformed pyproject.toml logs debug and falls through to dir scan."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[[invalid toml")
        src = tmp_path / "src"
        src.mkdir()
        (src / "mypkg").mkdir()
        (src / "mypkg" / "__init__.py").touch()
        assert detect_first_party_packages(tmp_path) == ["mypkg"]

    def test_empty_src_directory(self, tmp_path: Path) -> None:
        """Empty src/ directory returns empty list."""
        (tmp_path / "src").mkdir()
        assert detect_first_party_packages(tmp_path) == []

    def test_deptry_config_short_circuits(self, tmp_path: Path) -> None:
        """When known_first_party is already configured, return [] immediately."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.deptry]\nknown_first_party = ["existing"]\n')
        src = tmp_path / "src"
        src.mkdir()
        (src / "mypkg").mkdir()
        (src / "mypkg" / "__init__.py").touch()
        assert detect_first_party_packages(tmp_path) == []
