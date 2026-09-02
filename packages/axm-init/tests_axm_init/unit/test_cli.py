"""Unit regression guard for the package surface after facade removal."""

from __future__ import annotations

import axm_init


def test_package_surface_does_not_export_cli_facade() -> None:
    """The root API exposes only the package version, never the old facade."""
    assert axm_init.__all__ == ["__version__"]
    assert not hasattr(axm_init, "cli")
