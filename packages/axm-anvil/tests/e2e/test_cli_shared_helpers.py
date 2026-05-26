from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_cli_shared_helpers_error_mode(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n    return 1\n\n"
        "def moved_A():\n    return _shared()\n\n"
        "def remaining_B():\n    return _shared()\n"
    )
    target.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm_anvil",
            "move",
            str(source),
            str(target),
            "moved_A",
            "--shared-helpers",
            "error",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "shared" in combined
    assert "_shared" in result.stderr + result.stdout


@pytest.mark.e2e
def test_cli_shared_helpers_invalid_choice(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text("def foo():\n    return 1\n")
    target.write_text("")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "axm_anvil",
            "move",
            str(source),
            str(target),
            "foo",
            "--shared-helpers",
            "extract",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
