from __future__ import annotations

from pathlib import Path

import pytest

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

    @pytest.mark.parametrize(
        "pyproject_content",
        [
            pytest.param(None, id="no_pyproject"),
            pytest.param("[project]\nname = 'foo'\n", id="without_deptry_section"),
            pytest.param("[[invalid toml content", id="malformed_toml"),
        ],
    )
    def test_does_not_short_circuit(
        self, tmp_path: Path, pyproject_content: str | None
    ) -> None:
        self._seed_src_pkg(tmp_path)
        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        assert detect_first_party_packages(tmp_path) == ["mypkg"]


class TestDetectFirstPartyEdgeCases:
    """Edge-case tests for detect_first_party_packages."""

    def test_empty_src_directory(self, tmp_path: Path) -> None:
        """Empty src/ directory returns empty list."""
        (tmp_path / "src").mkdir()
        assert detect_first_party_packages(tmp_path) == []
