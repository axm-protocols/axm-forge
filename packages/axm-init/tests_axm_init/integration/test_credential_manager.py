"""Tests for CredentialManager — get/save/validate + resolve_pypi_token."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import keyring
import pytest
from axm_vault import KeyringStore
from keyring.backend import KeyringBackend

from axm_init.adapters.credentials import CredentialManager


class _MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._values.pop((service, username), None)


class TestCredentialManager:
    """Tests for credential management with real filesystem I/O."""

    @pytest.mark.integration
    def test_save_pypi_token_stores_declared_vault_credential(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC1: saving stores the token under its declared vault credential."""
        _ = """save_pypi_token returns False on PermissionError."""
        token = "pypi-AgEIcHlwaS5vcmc-written"
        monkeypatch.setenv("HOME", str(tmp_path))
        catalog_module = importlib.import_module("axm_init.credentials_catalog")
        group = catalog_module.pypi_credentials()[0]
        spec = next(spec for spec in group.specs if spec.env == "PYPI_API_TOKEN")
        previous_backend = keyring.get_keyring()
        keyring.set_keyring(_MemoryKeyring())
        try:
            manager = CredentialManager()
            assert manager.save_pypi_token(token) is True
            assert KeyringStore().get(group.id, spec.name) == token
        finally:
            keyring.set_keyring(previous_backend)

    def test_get_pypi_token_from_pypirc(self, tmp_path: Path) -> None:
        """Token from ~/.pypirc when env not set."""
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
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PYPI_API_TOKEN", None)
            manager = CredentialManager(pypirc_path=tmp_path / "nonexistent")
            token = manager.get_pypi_token()
            assert token is None


# ── resolve_pypi_token ───────────────────────────────────────────────────────


class TestResolvePypiToken:
    """resolve_pypi_token() — env → .pypirc → prompt → persist."""

    def test_pypirc_fallback(self, tmp_path: Path) -> None:
        """Reads from .pypirc when no env var."""
        pypirc = tmp_path / ".pypirc"
        pypirc.write_text("[pypi]\nusername = __token__\npassword = pypi-from-file\n")

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PYPI_API_TOKEN", None)
            creds = CredentialManager(pypirc_path=pypirc)
            token = creds.resolve_pypi_token()
            assert token == "pypi-from-file"

    @pytest.mark.integration
    def test_save_pypi_token_does_not_create_pypirc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC2: saving a token never creates ~/.pypirc."""
        _ = """Prompts user, saves token to .pypirc with 0o600 permissions."""
        token = "pypi-AgEIcHlwaS5vcmc-no-file"
        monkeypatch.setenv("HOME", str(tmp_path))
        previous_backend = keyring.get_keyring()
        keyring.set_keyring(_MemoryKeyring())
        try:
            manager = CredentialManager()
            assert manager.save_pypi_token(token) is True
            assert not (tmp_path / ".pypirc").exists()
        finally:
            keyring.set_keyring(previous_backend)

    @pytest.mark.integration
    def test_save_pypi_token_preserves_existing_pypirc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC2: saving a token leaves an existing ~/.pypirc unchanged."""
        _ = """Existing [testpypi] section survives when [pypi] is added."""
        pypirc = tmp_path / ".pypirc"
        original = "[testpypi]\nusername = __token__\npassword = pypi-test-token\n"
        pypirc.write_text(original)
        monkeypatch.setenv("HOME", str(tmp_path))
        previous_backend = keyring.get_keyring()
        keyring.set_keyring(_MemoryKeyring())
        try:
            manager = CredentialManager()
            assert manager.save_pypi_token("pypi-AgEIcHlwaS5vcmc-preserve") is True
            assert pypirc.read_text() == original
        finally:
            keyring.set_keyring(previous_backend)

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

    @pytest.mark.integration
    def test_vault_token_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: vault supplies a token when env and .pypirc are absent."""
        _ = """AC2: vault supplies PyPI token when env and .pypirc are absent."""
        token = "pypi-AgEIcHlwaS5vcmc-vault"
        monkeypatch.delenv("PYPI_API_TOKEN", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        catalog_module = importlib.import_module("axm_init.credentials_catalog")
        group = catalog_module.pypi_credentials()[0]
        spec = next(spec for spec in group.specs if spec.env == "PYPI_API_TOKEN")
        previous_backend = keyring.get_keyring()
        keyring.set_keyring(_MemoryKeyring())
        try:
            KeyringStore().set(group.id, spec.name, token)
            manager = CredentialManager()
            assert manager.resolve_pypi_token(interactive=False) == token
        finally:
            keyring.set_keyring(previous_backend)
