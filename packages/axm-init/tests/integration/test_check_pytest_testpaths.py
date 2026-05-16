"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_pytest_testpaths


class TestPytestTestpaths:
    """Tests for check_pytest_testpaths."""

    def test_testpaths_present(self, tmp_path: Path) -> None:
        """testpaths with member test dirs passes."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["packages/pkg-a/tests"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert result.passed

    def test_testpaths_missing(self, ws_root: Path) -> None:
        """No testpaths configuration → fails."""
        result = check_pytest_testpaths(ws_root)
        assert not result.passed
        assert "testpaths" in result.message.lower()


class TestPytestTestpathsEdge:
    """Cover lines 384, 421: no pyproject and testpaths without packages."""

    def test_no_pyproject_fails(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_pytest_testpaths

        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "No pyproject.toml" in result.message

    def test_testpaths_without_packages_ref(self, tmp_path: Path) -> None:
        """testpaths that don't reference packages/*/tests → fails."""
        from axm_init.checks.workspace import check_pytest_testpaths

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests/", "integration/"]\n'
        )
        result = check_pytest_testpaths(tmp_path)
        assert not result.passed
        assert "does not reference" in result.message
