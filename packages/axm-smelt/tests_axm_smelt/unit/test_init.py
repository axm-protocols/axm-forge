"""Public API regressions formerly colocated with the retired CLI tests."""

from __future__ import annotations

import axm_smelt


def test_public_api_remains_available() -> None:
    """Removing the façade preserves the package-level API."""
    assert isinstance(axm_smelt.__version__, str)
    assert {"smelt", "check", "count"} <= set(axm_smelt.__all__)
