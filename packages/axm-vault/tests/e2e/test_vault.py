"""E2E black-box tests for the ``axm-vault`` CLI (subprocess)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from axm_vault.store import KeyringStore

pytestmark = pytest.mark.e2e

_VAULT = (sys.executable, "-m", "axm_vault")


def test_path_prints_home() -> None:
    """AC4: ``axm-vault path`` prints the ~/.axm home directory."""
    proc = subprocess.run([*_VAULT, "path"], capture_output=True, text=True, check=True)
    assert proc.stdout.strip().endswith("/.axm")


def test_doctor_no_secret_values() -> None:
    """AC4: ``axm-vault doctor`` exits 0 and never prints a plaintext secret."""
    KeyringStore().set("e2e", "probe", "PLAINTEXT-SECRET-E2E")
    try:
        proc = subprocess.run(
            [*_VAULT, "doctor"], capture_output=True, text=True, check=False
        )
    finally:
        KeyringStore().delete("e2e", "probe")
    assert proc.returncode == 0
    assert "PLAINTEXT-SECRET-E2E" not in proc.stdout


def test_help_lists_commands_no_import() -> None:
    """AC4: ``--help`` lists the 6 commands and never advertises 'import'."""
    proc = subprocess.run(
        [*_VAULT, "--help"], capture_output=True, text=True, check=True
    )
    out = proc.stdout
    for command in ("setup", "get", "set", "rotate", "doctor", "path"):
        assert command in out
    assert "import" not in out
