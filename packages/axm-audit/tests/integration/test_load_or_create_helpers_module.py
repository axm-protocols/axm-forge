"""Integration tests for load_or_create_helpers_module."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import load_or_create_helpers_module

pytestmark = pytest.mark.integration


def test_existing_helpers_module_is_loaded_not_overwritten(tmp_path: Path) -> None:
    """load_or_create_helpers_module reads an existing file verbatim."""
    helpers_path = tmp_path / "_helpers.py"
    helpers_path.write_text("SENTINEL = 1\n")

    module = load_or_create_helpers_module(helpers_path, "unit", "tests.unit._helpers")

    assert module is not None
    assert "SENTINEL = 1" in module.code
