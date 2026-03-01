"""Credential Manager — handles PyPI and GitHub authentication.

Reads tokens from environment variables and config files,
with support for interactive prompting when tokens are missing.

Resolves values with priority: env var > config file > interactive prompt.
"""

from __future__ import annotations

import configparser
import getpass
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


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

        try:
            import io

            buf = io.StringIO()
            config.write(buf)
            self.pypirc_path.write_text(buf.getvalue())
            # Set restrictive permissions
            self.pypirc_path.chmod(0o600)
        except (PermissionError, OSError) as exc:
            logger.warning("Failed to save %s: %s", self.pypirc_path, exc)
            return False
        return True

    def resolve_pypi_token(self, *, interactive: bool = True) -> str:
        """Resolve PyPI token: env → .pypirc → prompt → save.

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
        self.save_pypi_token(token)
        print(f"✅ Saved to {self.pypirc_path}")  # noqa: T201
        return token
