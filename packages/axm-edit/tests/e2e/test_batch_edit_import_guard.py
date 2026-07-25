"""E2E: the ``axm batch_edit_import_guard`` CLI reports orphan imports.

Black-box invocation of the auto-generated CLI command proving the tool is
discoverable (listed in the ``axm`` catalog) and runnable end-to-end on a
sample op set passed as a JSON string.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _axm_bin() -> str:
    """Locate the ``axm`` console script (PATH, else beside the interpreter)."""
    found = shutil.which("axm")
    if found:
        return found
    candidate = Path(sys.executable).parent / "axm"
    if candidate.exists():
        return str(candidate)
    pytest.skip("axm console script not found on PATH or in venv")


@pytest.mark.e2e
def test_cli_tool_is_listed_in_the_axm_catalog() -> None:
    """The tool appears in the ``axm`` command catalog (entry-point metadata)."""
    proc = subprocess.run(
        [_axm_bin()],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "batch_edit_import_guard" in proc.stdout


@pytest.mark.e2e
def test_cli_runs_on_a_sample_op_set_and_prints_the_verdict() -> None:
    """Invoking the CLI on a clean op set exits 0 and prints the verdict."""
    operations = [
        {
            "op": "create",
            "file": "m.py",
            "content": "from mod import Widget\nw = Widget()\n",
        },
    ]

    proc = subprocess.run(
        [
            _axm_bin(),
            "batch_edit_import_guard",
            "--path",
            ".",
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "batch_edit_import_guard" in proc.stdout
