"""Tests for version management."""

import re


def test_version_import() -> None:
    """Test that __version__ is importable from axm package."""
    from axm_init import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)


def test_version_format_is_pep440() -> None:
    """Test that version string follows PEP 440 format."""
    from axm_init import __version__

    # PEP 440 pattern: N[.N]+[{a|b|rc}N][.postN][.devN][+local]
    pep440_pattern = r"^\d+(\.\d+)*(\.dev\d+|a\d+|b\d+|rc\d+)?(\+.+)?$"
    assert re.match(pep440_pattern, __version__), (
        f"Invalid PEP 440 version: {__version__}"
    )


def test_version_from_module() -> None:
    """Test that _version module exists and exports __version__."""
    from axm_init._version import __version__

    assert __version__ is not None
