"""Integration tests for load_or_create_conftest_module."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import load_or_create_conftest_module

pytestmark = pytest.mark.integration


def test_existing_conftest_module_is_loaded_not_overwritten(tmp_path: Path) -> None:
    """load_or_create_conftest_module reads an existing file verbatim."""
    conftest_path = tmp_path / "conftest.py"
    conftest_path.write_text("MARKER = 'kept'\n")

    module = load_or_create_conftest_module(conftest_path)

    assert module is not None
    assert "MARKER = 'kept'" in module.code
