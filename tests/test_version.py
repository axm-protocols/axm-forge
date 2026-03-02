"""Test package version is accessible."""

from axm import __version__

_MIN_SEMVER_PARTS = 3


def test_version_is_string() -> None:
    """Version should be a valid string."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_format() -> None:
    """Version should follow semver pattern."""
    parts = __version__.replace("a", ".").replace("b", ".").split(".")
    assert len(parts) >= _MIN_SEMVER_PARTS
