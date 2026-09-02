"""Unit tests for CredentialManager (no real I/O)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from axm_init.adapters.credentials import CredentialManager


class TestCredentialManagerUnit:
    """Pure-logic tests for CredentialManager (no real I/O)."""

    def test_get_pypi_token_from_env(self) -> None:
        """Token from PYPI_API_TOKEN env var takes priority."""
        with patch.dict(os.environ, {"PYPI_API_TOKEN": "pypi-test-token"}):
            manager = CredentialManager()
            token = manager.get_pypi_token()
            assert token == "pypi-test-token"

    def test_pypirc_path_constructor_keyword_is_rejected(self) -> None:
        """AC4: no constructor parameter can designate an INI token source."""
        constructor = Mock(wraps=CredentialManager)
        with pytest.raises(TypeError):
            constructor(pypirc_path=Path("/tmp/whatever"))

    def test_validate_token_format(self) -> None:
        """Validates pypi- token prefix."""
        manager = CredentialManager()
        assert manager.validate_token("pypi-abc123") is True
        assert manager.validate_token("invalid-token") is False
        assert manager.validate_token("") is False

    def test_env_var_takes_priority(self) -> None:
        """resolve_pypi_token: PYPI_API_TOKEN env var returns immediately, no prompt."""
        with patch.dict(os.environ, {"PYPI_API_TOKEN": "pypi-env-token"}):
            creds = CredentialManager()
            token = creds.resolve_pypi_token()
            assert token == "pypi-env-token"
