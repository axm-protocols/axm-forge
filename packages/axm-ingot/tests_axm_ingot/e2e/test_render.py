"""E2E test: the render surface is importable from the installed package."""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e


def test_render_surface_importable_via_installed_package() -> None:
    script = (
        "import axm_ingot; "
        "assert axm_ingot.render is not None; "
        "from axm_ingot import header, labeled_block, compact_table, "
        "truncate, format_count, format_size; "
        "print(header('t', 's'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "t | s" in result.stdout
