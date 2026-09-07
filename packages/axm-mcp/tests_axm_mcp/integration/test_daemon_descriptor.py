from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.integration
def test_declared_daemon_entry_point_is_importable_and_equivalent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: declare one importable daemon target matching the public function."""
    monkeypatch.setenv("AXM_PROFILE", "production")
    package_root = Path(__file__).parents[2]
    with (package_root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)

    entries = pyproject["project"]["entry-points"]["axm.daemons"]
    assert entries == {"axm-mcp": "axm_mcp.daemon:daemon_descriptor"}

    target = next(iter(entries.values()))
    module_name, attribute_name = target.split(":", maxsplit=1)
    declared_module: ModuleType = importlib.import_module(module_name)
    declared_descriptor = getattr(declared_module, attribute_name)
    public_module: ModuleType = importlib.import_module("axm_mcp.daemon")

    assert declared_descriptor() == public_module.daemon_descriptor()
