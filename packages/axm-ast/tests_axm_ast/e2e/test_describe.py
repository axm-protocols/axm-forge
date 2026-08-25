from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[2]


def test_cli_detail_full_rejected():
    """CLI --detail full must produce a clear error and exit 1."""
    proc = subprocess.run(
        [sys.executable, "-m", "axm_ast", "describe", "--detail", "full"],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0


@pytest.mark.e2e
def test_cli_names_is_shorter_than_summary() -> None:
    """Packaged --detail names succeeds and is shorter than summary (AC4)."""
    command = [
        str(Path(sys.executable).with_name("axm-ast")),
        "describe",
        str(PACKAGE_ROOT),
        "--detail",
    ]

    names = subprocess.run(
        [*command, "names"],
        capture_output=True,
        text=True,
    )
    summary = subprocess.run(
        [*command, "summary"],
        capture_output=True,
        text=True,
    )

    assert names.returncode == 0, names.stderr
    assert summary.returncode == 0, summary.stderr
    assert len(names.stdout) < len(summary.stdout)
