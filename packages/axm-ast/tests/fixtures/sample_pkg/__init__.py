"""A sample Python module for testing AST parsing.

This module demonstrates various Python constructs that
the parser must handle correctly.
"""

from __future__ import annotations

from pathlib import Path  # noqa: F401 (used by parser test)
from typing import Any

__all__ = ["Calculator", "greet"]

MAX_RETRIES: int = 3
DEFAULT_NAME = "world"


def greet(name: str = "world") -> str:
    """Return a greeting message.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"


def _internal_helper(data: dict[str, Any]) -> bool:
    """Private helper function."""
    return bool(data)


async def fetch_data(url: str, *, timeout: int = 30) -> dict[str, Any]:
    """Fetch data from a URL asynchronously.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        Response data as dictionary.
    """
    return {"url": url, "timeout": timeout}


class Calculator:
    """A simple calculator class.

    Example:
        >>> calc = Calculator()
        >>> calc.add(1, 2)
        3
    """

    def __init__(self, precision: int = 2) -> None:
        """Initialize calculator."""
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return round(a + b, self.precision)

    @property
    def name(self) -> str:
        """Calculator name."""
        return "Calculator"

    @staticmethod
    def version() -> str:
        """Return version string."""
        return "1.0"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> Calculator:
        """Create from config dict."""
        return cls(precision=config.get("precision", 2))


class _InternalClass:
    """Private internal class."""

    def run(self) -> None:
        """Run internal logic."""
