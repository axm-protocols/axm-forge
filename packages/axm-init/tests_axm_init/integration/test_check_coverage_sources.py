"""Integration: ``workspace.coverage_sources`` against real workspace layouts."""

from pathlib import Path

import pytest

from axm_init.checks.workspace import check_coverage_sources


def _member(root: Path, name: str, *modules: str) -> None:
    """Create ``packages/<name>`` with one src package per module."""
    member = root / "packages" / name
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    for module in modules or (name.replace("-", "_"),):
        package = member / "src" / module
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")


def _root(root: Path, coverage: str = "") -> Path:
    """Write the workspace root manifest with an optional coverage block."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        f"{coverage}"
    )
    return root


class TestCheckCoverageSources:
    """Tests for check_coverage_sources."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        result = check_coverage_sources(tmp_path)
        assert not result.passed
        assert result.name == "workspace.coverage_sources"
        assert "No pyproject.toml" in result.message

    def test_absent_key_passes(self, tmp_path: Path) -> None:
        _member(tmp_path, "alpha")
        result = check_coverage_sources(_root(tmp_path))
        assert result.passed
        assert result.category == "workspace"

    def test_unrelated_coverage_keys_pass(self, tmp_path: Path) -> None:
        _member(tmp_path, "alpha")
        root = _root(tmp_path, "[tool.coverage.run]\nbranch = true\n")
        assert check_coverage_sources(root).passed

    @pytest.mark.parametrize("key", ["source", "source_pkgs"])
    def test_explicit_empty_list_fails(self, tmp_path: Path, key: str) -> None:
        _member(tmp_path, "alpha")
        result = check_coverage_sources(
            _root(tmp_path, f"[tool.coverage.run]\n{key} = []\n")
        )
        assert not result.passed
        assert key in result.message
        assert "Remove the empty key" in result.fix

    @pytest.mark.parametrize(
        "entries",
        [
            '["alpha", "beta_pkg"]',
            '["packages/alpha/src/alpha", "packages/beta-pkg/src/beta_pkg"]',
            '["./packages/*/src"]',
            '["packages"]',
        ],
    )
    def test_full_list_passes(self, tmp_path: Path, entries: str) -> None:
        _member(tmp_path, "alpha")
        _member(tmp_path, "beta-pkg")
        root = _root(tmp_path, f"[tool.coverage.run]\nsource = {entries}\n")
        assert check_coverage_sources(root).passed

    def test_drift_names_missing_module(self, tmp_path: Path) -> None:
        _member(tmp_path, "alpha")
        _member(tmp_path, "beta-pkg")
        root = _root(tmp_path, '[tool.coverage.run]\nsource_pkgs = ["alpha"]\n')
        result = check_coverage_sources(root)
        assert not result.passed
        assert result.details == ["beta-pkg: beta_pkg"]

    def test_source_and_source_pkgs_are_combined(self, tmp_path: Path) -> None:
        _member(tmp_path, "alpha")
        _member(tmp_path, "beta-pkg")
        root = _root(
            tmp_path,
            '[tool.coverage.run]\nsource = ["alpha"]\nsource_pkgs = ["beta_pkg"]\n',
        )
        assert check_coverage_sources(root).passed

    def test_directory_without_pyproject_is_ignored(self, tmp_path: Path) -> None:
        """A directory without pyproject.toml is not a member and cannot cause drift."""
        _member(tmp_path, "alpha")
        (tmp_path / "other").mkdir()
        root = _root(tmp_path, '[tool.coverage.run]\nsource = ["alpha"]\n')
        assert check_coverage_sources(root).passed

    def test_excluded_member_cannot_cause_drift(self, tmp_path: Path) -> None:
        """Members excluded from the workspace are not expected in the sources."""
        _member(tmp_path, "alpha")
        _member(tmp_path, "skipped")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            'exclude = ["packages/skipped"]\n'
            '[tool.coverage.run]\nsource = ["alpha"]\n'
        )
        assert check_coverage_sources(tmp_path).passed
