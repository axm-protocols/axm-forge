"""E2E: ``axm search_files`` bounds output on a minified single-line file."""

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
def test_cli_search_minified_output_bounded(tmp_path: Path) -> None:
    blob = ";".join(f"var a{i}=needle{i}" for i in range(20000))
    (tmp_path / "app.min.js").write_text(blob, encoding="utf-8")

    proc = subprocess.run(
        [
            _axm_bin(),
            "search_files",
            "--path",
            str(tmp_path),
            "--pattern",
            "needle",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    # The full multi-hundred-KB minified line must not be embedded verbatim.
    assert blob not in proc.stdout
    assert len(proc.stdout) < len(blob)
    assert "truncated" in proc.stdout
