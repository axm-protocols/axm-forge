"""E2E test for the ``axm anvil_rename`` CLI (subprocess black box)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_rename_old_new(tmp_path: Path) -> None:
    """AC1, AC2: ``axm anvil_rename --old Foo --new Bar`` rewrites the file."""
    mod = tmp_path / "mod.py"
    mod.write_text(
        "def Foo() -> int:\n    return 1\n\n\ndef use() -> int:\n    return Foo()\n"
    )

    proc = subprocess.run(
        [
            "axm",
            "anvil_rename",
            "--path",
            str(tmp_path),
            "--file",
            "mod.py",
            "--old",
            "Foo",
            "--new",
            "Bar",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    text = mod.read_text()
    assert "def Bar()" in text
    assert "return Bar()" in text
    assert "Foo" not in text
