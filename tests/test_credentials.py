"""Tests for CredentialManager — RED phase."""

import os
from pathlib import Path
from unittest.mock import patch


class TestCredentialManager:
    """Tests for credential management."""

    def test_get_pypi_token_from_env(self) -> None:
        """Token from PYPI_API_TOKEN env var takes priority."""
        from axm_init.adapters.credentials import CredentialManager

        with patch.dict(os.environ, {"PYPI_API_TOKEN": "pypi-test-token"}):
            manager = CredentialManager()
            token = manager.get_pypi_token()
            assert token == "pypi-test-token"

    def test_get_pypi_token_from_pypirc(self, tmp_path: Path) -> None:
        """Token from ~/.pypirc when env not set."""
        from axm_init.adapters.credentials import CredentialManager

        pypirc = tmp_path / ".pypirc"
        pypirc.write_text("""[pypi]
username = __token__
password = pypi-from-file
""")

        with patch.dict(os.environ, {}, clear=True):
            # Remove PYPI_API_TOKEN if present
            os.environ.pop("PYPI_API_TOKEN", None)
            manager = CredentialManager(pypirc_path=pypirc)
            token = manager.get_pypi_token()
            assert token == "pypi-from-file"

    def test_get_pypi_token_missing(self, tmp_path: Path) -> None:
        """Returns None when no token available."""
        from axm_init.adapters.credentials import CredentialManager

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PYPI_API_TOKEN", None)
            manager = CredentialManager(pypirc_path=tmp_path / "nonexistent")
            token = manager.get_pypi_token()
            assert token is None

    def test_validate_token_format(self) -> None:
        """Validates pypi- token prefix."""
        from axm_init.adapters.credentials import CredentialManager

        manager = CredentialManager()
        assert manager.validate_token("pypi-abc123") is True
        assert manager.validate_token("invalid-token") is False
        assert manager.validate_token("") is False
