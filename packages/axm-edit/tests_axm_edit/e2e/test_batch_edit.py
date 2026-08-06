"""E2E tests for the ``axm batch_edit`` console script (subprocess black box)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

NBSP = chr(0xA0)  # U+00A0 NO-BREAK SPACE (built, so the source stays ASCII)


def _axm_binary() -> Path:
    """Resolve the ``axm`` console script of the current environment.

    ``axm`` is a declared dependency of ``axm-edit``: a missing binary is a
    genuine failure, never a reason to skip.
    """
    found = shutil.which("axm")
    binary = Path(found) if found else Path(sys.executable).with_name("axm")
    assert binary.exists(), f"axm console script not found at {binary}"
    return binary


@pytest.mark.e2e
def test_batch_edit_reports_nbsp_near_miss_with_locator(tmp_path: Path) -> None:
    """AC4: the CLI exits non-zero and prints a locator-prefixed line + <NBSP>."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    # Line 4 differs from the requested ``old`` only by a U+00A0.
    target.write_text(f"import os\n\n\nvalue{NBSP}= 1\n", encoding="utf-8")

    operations = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"old": "value = 1", "new": "value = 2"}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit",
            "--path",
            str(tmp_path),
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )

    combined = proc.stdout + proc.stderr
    lines = [line.lstrip() for line in combined.splitlines()]

    assert proc.returncode != 0, combined
    assert any(line.startswith("pkg/mod.py:4:") for line in lines), combined
    assert "<NBSP>" in combined, combined
