"""E2E tests for the ``axm batch_edit_check`` console script (subprocess)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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
def test_batch_edit_check_help_exposes_the_operations_option() -> None:
    """AC2: ``axm batch_edit_check --help`` exits 0 and documents operations."""
    proc = subprocess.run(
        [str(_axm_binary()), "batch_edit_check", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    combined = proc.stdout + proc.stderr

    assert proc.returncode == 0, combined
    assert "operations" in proc.stdout, combined


@pytest.mark.e2e
def test_batch_edit_check_reports_zero_diagnostics_on_valid_operations(
    tmp_path: Path,
) -> None:
    """AC3: a nominal run exits 0 and announces ``0 diagnostic(s)``."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

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
            "batch_edit_check",
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

    assert proc.returncode == 0, combined
    assert "0 diagnostic(s)" in combined, combined


@pytest.mark.e2e
def test_batch_edit_check_prints_the_blocking_summary_line(tmp_path: Path) -> None:
    """AC4: a batch with an unknown edit key prints `blocking: yes`."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    operations: list[dict[str, object]] = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"old": "value = 1", "new": "value = 2", "replace_all": True}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit_check",
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

    assert "blocking: yes" in proc.stdout, combined
