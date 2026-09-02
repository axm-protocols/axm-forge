"""Integration regression guard for the removed CLI module."""

from __future__ import annotations

from importlib.util import find_spec

import pytest

pytestmark = pytest.mark.integration


def test_removed_cli_module_has_no_import_spec() -> None:
    """Package discovery no longer exposes a module for the deleted facade."""
    assert find_spec("axm_init.cli") is None
