"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_pytest_importmode


class TestPytestImportmode:
    """Tests for check_pytest_importmode."""

    def test_importmode_present(self, tmp_path: Path) -> None:
        """import_mode = 'importlib' passes."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'import_mode = "importlib"\n'
        )
        result = check_pytest_importmode(tmp_path)
        assert result.passed

    def test_importmode_missing(self, ws_root: Path) -> None:
        """No import_mode configuration → fails."""
        result = check_pytest_importmode(ws_root)
        assert not result.passed
        assert "importlib" in result.message


class TestPytestImportmodeNoToml:
    """Cover line 345: no pyproject.toml at root."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_pytest_importmode

        result = check_pytest_importmode(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message
