from __future__ import annotations

from collections.abc import Callable
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


def _setup_src_layout(root: Path) -> None:
    (root / "src" / "axm_foo").mkdir(parents=True)
    (root / "src" / "axm_foo" / "__init__.py").touch()


def _setup_namespace(root: Path) -> None:
    (root / "src" / "openleaf" / "performance").mkdir(parents=True)
    (root / "src" / "openleaf" / "performance" / "__init__.py").touch()


def _setup_no_src(root: Path) -> None:
    (root / "mypkg").mkdir()
    (root / "mypkg" / "__init__.py").touch()


def _setup_existing_config(root: Path) -> None:
    (root / "src" / "foo").mkdir(parents=True)
    (root / "src" / "foo" / "__init__.py").touch()
    (root / "pyproject.toml").write_text('[tool.deptry]\nknown_first_party = ["foo"]\n')


def _setup_flat_layout_with_excluded(root: Path) -> None:
    (root / "mypkg").mkdir()
    (root / "mypkg" / "__init__.py").touch()
    (root / "tests").mkdir()
    (root / "tests" / "__init__.py").touch()
    (root / "docs").mkdir()


def _setup_empty_src(root: Path) -> None:
    (root / "src").mkdir()


def _setup_src_only_pycache(root: Path) -> None:
    (root / "src" / "__pycache__").mkdir(parents=True)


def _setup_deep_namespace(root: Path) -> None:
    (root / "src" / "a" / "b" / "c").mkdir(parents=True)
    (root / "src" / "a" / "b" / "c" / "__init__.py").touch()


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param(_setup_src_layout, ["axm_foo"], id="src_layout"),
        pytest.param(_setup_namespace, ["openleaf"], id="namespace_package"),
        pytest.param(_setup_no_src, ["mypkg"], id="flat_no_src"),
        pytest.param(_setup_existing_config, [], id="skips_existing_config"),
        pytest.param(
            _setup_flat_layout_with_excluded,
            ["mypkg"],
            id="flat_layout_excludes_tests_docs",
        ),
        pytest.param(_setup_empty_src, [], id="empty_src"),
        pytest.param(_setup_src_only_pycache, [], id="src_only_pycache"),
        pytest.param(_setup_deep_namespace, ["a"], id="deep_namespace_top_level"),
    ],
)
def test_detect_first_party_packages(
    tmp_path: Path,
    setup: Callable[[Path], None],
    expected: list[str],
) -> None:
    """detect_first_party_packages handles src/flat/namespace/edge layouts."""
    setup(tmp_path)

    result = detect_first_party_packages(tmp_path)

    assert result == expected


def test_detect_first_party_multiple(tmp_path: Path) -> None:
    """Multiple packages under src/ are all detected."""
    for name in ("pkg_a", "pkg_b"):
        (tmp_path / "src" / name).mkdir(parents=True)
        (tmp_path / "src" / name / "__init__.py").touch()

    result = detect_first_party_packages(tmp_path)

    assert sorted(result) == ["pkg_a", "pkg_b"]
