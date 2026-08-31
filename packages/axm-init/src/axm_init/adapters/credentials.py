"""Credential Manager — handles PyPI and GitHub authentication.

Reads tokens from environment variables and config files,
with support for interactive prompting when tokens are missing.

Resolves values with priority: env var > config file > interactive prompt.
"""

from __future__ import annotations

import configparser
import getpass
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from axm_vault import KeyringStore, MissingCredentialError, as_secret, resolver

from axm_init.credentials_catalog import pypi_credentials

logger = logging.getLogger(__name__)


@dataclass
class CredentialManager:
    """Manages credentials for PyPI and GitHub operations.

    Token resolution order:
    1. PYPI_API_TOKEN environment variable
    2. axm-vault
    3. ~/.pypirc [pypi] password field
    """

    pypirc_path: Path = field(default_factory=lambda: Path.home() / ".pypirc")

    def get_pypi_token(self) -> str | None:
        """Get PyPI API token from environment or config file.

        Returns:
            Token string if found, None otherwise.
        """
        group = pypi_credentials()[0]
        try:
            resolved = resolver.resolve(group, "token")
        except MissingCredentialError:
            pass
        else:
            if resolved.value is not None:
                secret = as_secret(resolved.value)
                assert secret is not None
                return secret.get_secret_value()

        # Final fallback: ~/.pypirc uses its own INI format.
        if self.pypirc_path.exists():
            config = configparser.ConfigParser()
            config.read(self.pypirc_path)

            for section in ["pypi", "server-login"]:
                if config.has_section(section):
                    if config.has_option(section, "password"):
                        return config.get(section, "password")

        return None

    def validate_token(self, token: str) -> bool:
        """Validate PyPI token format.

        Args:
            token: Token string to validate.

        Returns:
            True if token has valid pypi- prefix.
        """
        if not token:
            return False
        return token.startswith("pypi-")

    def save_pypi_token(self, token: str) -> bool:
        """Save the PyPI token to its declared axm-vault credential.

        Args:
            token: Token to save.

        Returns:
            True if saved successfully.
        """
        group = pypi_credentials()[0]
        spec = group.specs[0]
        secret = as_secret(token)
        assert secret is not None

        try:
            KeyringStore().set(group.id, spec.name, secret.get_secret_value())
        except RuntimeError:
            logger.warning(
                "Failed to save credential %s.%s to axm-vault; "
                "set %s or repair OS keyring access",
                group.id,
                spec.name,
                spec.env,
            )
            return False
        return True

    def resolve_pypi_token(self, *, interactive: bool = True) -> str:
        """Resolve PyPI token: env → vault → .pypirc → prompt → vault.

        Args:
            interactive: If True, prompt user when token is not configured.

        Returns:
            Token string.

        Raises:
            SystemExit: If no token available and not interactive.
        """
        token = self.get_pypi_token()
        if token:
            return token

        if not interactive or not sys.stdin.isatty():
            print(  # noqa: T201
                "Error: No PyPI token found.\n"
                "Set PYPI_API_TOKEN env var or add to ~/.pypirc.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        # Interactive prompt
        print(  # noqa: T201
            "No PyPI token found. Get one at https://pypi.org/manage/account/token/"
        )
        token = getpass.getpass("PyPI API token: ")

        if not self.validate_token(token):
            print(  # noqa: T201
                "Error: Invalid token (must start with 'pypi-').",
                file=sys.stderr,
            )
            raise SystemExit(1)

        # Persist
        if not self.save_pypi_token(token):
            print(  # noqa: T201
                "Warning: PyPI credential was not saved to axm-vault; "
                "set PYPI_API_TOKEN or repair OS keyring access.",
                file=sys.stderr,
            )
            return token
        print("✅ Saved PyPI credential to axm-vault")  # noqa: T201
        return token
