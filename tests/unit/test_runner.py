"""Unit tests for the runner module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_git.core.runner import detect_package_name, gh_available, run_gh, run_git


class TestRunGit:
    """Test run_git helper."""

    def test_success(self, tmp_path: Path) -> None:
        run_git(["init"], tmp_path)
        result = run_git(["status", "--short"], tmp_path)
        assert result.returncode == 0

    def test_failure_bad_dir(self, tmp_path: Path) -> None:
        result = run_git(["status"], tmp_path)
        assert result.returncode != 0

    def test_defaults(self, tmp_path: Path) -> None:
        """Verify default kwargs are applied."""
        run_git(["init"], tmp_path)
        result = run_git(["status"], tmp_path)
        # text=True → stdout is str
        assert isinstance(result.stdout, str)


class TestGhAvailable:
    """Test gh_available helper."""

    @patch("axm_git.core.runner.shutil.which", return_value=None)
    def test_gh_not_installed(self, _which: MagicMock) -> None:
        assert gh_available() is False

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_ok(self, _which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="", stderr=""
        )
        assert gh_available() is True

    @patch("axm_git.core.runner.subprocess.run")
    @patch("axm_git.core.runner.shutil.which", return_value="/usr/bin/gh")
    def test_gh_installed_auth_fail(
        self, _which: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="not logged in"
        )
        assert gh_available() is False


class TestRunGh:
    """Test run_gh helper."""

    @patch("axm_git.core.runner.subprocess.run")
    def test_run_gh_delegates(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="ok", stderr=""
        )
        result = run_gh(["auth", "status"], Path("/tmp"))
        assert result.returncode == 0
        assert result.stdout == "ok"
        mock_run.assert_called_once()


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
