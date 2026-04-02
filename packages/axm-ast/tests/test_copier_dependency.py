from __future__ import annotations

import importlib.metadata

import pytest
from packaging.version import Version


def test_copier_version_at_least_9_14_1() -> None:
    """AC1+AC2: copier dependency is bumped to >=9.14.1 (CVE fix)."""
    version = Version(importlib.metadata.version("copier"))
    assert version >= Version("9.14.1"), f"copier {version} < 9.14.1"


def test_existing_copier_usage(tmp_path: pytest.TempPathFactory) -> None:
    """AC3: copier public API still works after bump (smoke test)."""
    import copier

    # Verify core API entry points are still importable and callable
    assert callable(getattr(copier, "run_copy", None)), "copier.run_copy missing"
