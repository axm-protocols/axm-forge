"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_packages_layout


class TestPackagesLayout:
    """Tests for check_packages_layout."""

    def test_valid(self, ws_root: Path) -> None:
        """Members under packages/ passes."""
        result = check_packages_layout(ws_root)
        assert result.passed
        assert result.weight == 3

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid (workspace just configured)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_packages_layout(tmp_path)
        assert result.passed

    def test_members_outside_packages(self, tmp_path: Path) -> None:
        """Members not under packages/ fails."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["libs/*"]\n'
        )
        lib = tmp_path / "libs" / "pkg-a"
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_packages_layout(tmp_path)
        assert not result.passed
        assert "outside packages/" in result.message
