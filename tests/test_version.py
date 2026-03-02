"""Test package version is accessible."""

from __future__ import annotations

import re

from axm import __version__


def test_version_is_string() -> None:
    """Version should be a valid string."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_format() -> None:
    """Version should follow semver pattern (major.minor.patch with optional suffix)."""
    assert re.match(
        r"^\d+\.\d+\.\d+", __version__
    ), f"Version '{__version__}' does not match semver pattern"
