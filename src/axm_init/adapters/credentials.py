"""Credential Manager — handles PyPI and GitHub authentication.

Reads tokens from environment variables and config files,
with support for interactive prompting when tokens are missing.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CredentialManager:
    """Manages credentials for PyPI and GitHub operations.

    Token resolution order:
    1. PYPI_API_TOKEN environment variable
    2. ~/.pypirc [pypi] password field
    """

    pypirc_path: Path = field(default_factory=lambda: Path.home() / ".pypirc")

    def get_pypi_token(self) -> str | None:
        """Get PyPI API token from environment or config file.

        Returns:
            Token string if found, None otherwise.
        """
        # Priority 1: Environment variable
        if token := os.environ.get("PYPI_API_TOKEN"):
            return token

        # Priority 2: ~/.pypirc file
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
        """Save PyPI token to ~/.pypirc.

        Args:
            token: Token to save.

        Returns:
            True if saved successfully.
        """
        config = configparser.ConfigParser()

        if self.pypirc_path.exists():
            config.read(self.pypirc_path)

        if not config.has_section("pypi"):
            config.add_section("pypi")

        config.set("pypi", "username", "__token__")
        config.set("pypi", "password", token)

        with open(self.pypirc_path, "w") as f:
            config.write(f)

        # Set restrictive permissions
        self.pypirc_path.chmod(0o600)
        return True
