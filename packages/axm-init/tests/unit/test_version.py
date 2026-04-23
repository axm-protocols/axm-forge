"""Tests for version management."""

import re


def test_version_format_is_pep440() -> None:
    """Test that version string follows PEP 440 format."""
    from axm_init import __version__

    # PEP 440 pattern: N[.N]+[{a|b|rc}N][.postN][.devN][+local]
    pep440_pattern = r"^\d+(\.\d+)*(\.dev\d+|a\d+|b\d+|rc\d+)?(\+.+)?$"
    assert re.match(pep440_pattern, __version__), (
        f"Invalid PEP 440 version: {__version__}"
    )
