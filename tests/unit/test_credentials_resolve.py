"""Tests for CredentialManager.resolve_pypi_token — TDD RED phase."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_init.adapters.credentials import CredentialManager


class TestResolvePypiToken:
    """resolve_pypi_token() — env → .pypirc → prompt → persist."""

    def test_env_var_takes_priority(self) -> None:
        """PYPI_API_TOKEN env var returns immediately, no prompt."""
        with patch.dict(os.environ, {"PYPI_API_TOKEN": "pypi-env-token"}):
            creds = CredentialManager()
            token = creds.resolve_pypi_token()
            assert token == "pypi-env-token"

    def test_pypirc_fallback(self, tmp_path: Path) -> None:
        """Reads from .pypirc when no env var."""
        pypirc = tmp_path / ".pypirc"
        pypirc.write_text("[pypi]\nusername = __token__\npassword = pypi-from-file\n")

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PYPI_API_TOKEN", None)
            creds = CredentialManager(pypirc_path=pypirc)
            token = creds.resolve_pypi_token()
            assert token == "pypi-from-file"

    def test_prompt_saves_to_pypirc(self, tmp_path: Path) -> None:
        """Prompts user, saves token to .pypirc with 0o600 permissions."""
        pypirc = tmp_path / ".pypirc"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("getpass.getpass", return_value="pypi-user-token"),
            patch("sys.stdin") as mock_stdin,
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            mock_stdin.isatty.return_value = True
            creds = CredentialManager(pypirc_path=pypirc)
            token = creds.resolve_pypi_token()

        assert token == "pypi-user-token"
        assert pypirc.exists()
        content = pypirc.read_text()
        assert "pypi-user-token" in content
        assert pypirc.stat().st_mode & 0o777 == 0o600

    def test_prompt_preserves_existing_sections(self, tmp_path: Path) -> None:
        """Existing [testpypi] section survives when [pypi] is added."""
        pypirc = tmp_path / ".pypirc"
        pypirc.write_text(
            "[testpypi]\nusername = __token__\npassword = pypi-test-token\n"
        )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("getpass.getpass", return_value="pypi-new-token"),
            patch("sys.stdin") as mock_stdin,
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            mock_stdin.isatty.return_value = True
            creds = CredentialManager(pypirc_path=pypirc)
            token = creds.resolve_pypi_token()

        assert token == "pypi-new-token"
        content = pypirc.read_text()
        assert "testpypi" in content
        assert "pypi-test-token" in content

    def test_non_interactive_exits(self, tmp_path: Path) -> None:
        """interactive=False + no token → SystemExit(1)."""
        pypirc = tmp_path / "nonexistent"

        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(SystemExit),
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            creds = CredentialManager(pypirc_path=pypirc)
            creds.resolve_pypi_token(interactive=False)

    def test_non_tty_exits(self, tmp_path: Path) -> None:
        """Non-TTY stdin + no token → SystemExit(1)."""
        pypirc = tmp_path / "nonexistent"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.stdin") as mock_stdin,
            pytest.raises(SystemExit),
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            mock_stdin.isatty.return_value = False
            creds = CredentialManager(pypirc_path=pypirc)
            creds.resolve_pypi_token()

    def test_invalid_token_exits(self, tmp_path: Path) -> None:
        """Token without 'pypi-' prefix → SystemExit(1)."""
        pypirc = tmp_path / ".pypirc"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("getpass.getpass", return_value="not-a-valid-token"),
            patch("sys.stdin") as mock_stdin,
            pytest.raises(SystemExit),
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            mock_stdin.isatty.return_value = True
            creds = CredentialManager(pypirc_path=pypirc)
            creds.resolve_pypi_token()

    def test_empty_input_exits(self, tmp_path: Path) -> None:
        """Empty string input → SystemExit(1)."""
        pypirc = tmp_path / ".pypirc"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("getpass.getpass", return_value=""),
            patch("sys.stdin") as mock_stdin,
            pytest.raises(SystemExit),
        ):
            os.environ.pop("PYPI_API_TOKEN", None)
            mock_stdin.isatty.return_value = True
            creds = CredentialManager(pypirc_path=pypirc)
            creds.resolve_pypi_token()
