"""Black-box invocation of ``axm file_bytes`` through the installed binary."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_axm_file_bytes_cli_reports_verdict_and_sha256(tmp_path: Path) -> None:
    """AC9: the CLI exits 0 and prints the verdict word and the sha256."""
    target = tmp_path / "cli.txt"
    payload = b"caf\xc3\xa9 cli\n"
    target.write_bytes(payload)
    expected_sha = hashlib.sha256(payload).hexdigest()

    completed = subprocess.run(
        ["axm", "file_bytes", "--path", str(target)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "verdict" in completed.stdout.lower()
    assert expected_sha in completed.stdout
