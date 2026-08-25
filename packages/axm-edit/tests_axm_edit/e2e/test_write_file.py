"""E2E: the ``axm write_file`` CLI confines writes to the project root."""

from __future__ import annotations

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
def test_cli_write_outside_root_exits_non_zero(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "escapee.txt"

    proc = subprocess.run(
        [
            _axm_bin(),
            "write_file",
            "--path",
            str(root),
            "--file",
            str(outside),
            "--content",
            "leak",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "confinement" in proc.stderr
    assert not outside.exists()


@pytest.mark.e2e
def test_cli_in_root_write_succeeds(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    proc = subprocess.run(
        [
            _axm_bin(),
            "write_file",
            "--path",
            str(root),
            "--file",
            "sub/out.txt",
            "--content",
            "ok",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert (root / "sub" / "out.txt").read_text() == "ok"
