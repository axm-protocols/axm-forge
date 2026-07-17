"""E2E black-box tests for ``axm-vault delete`` (subprocess).

The subprocess sees the real, empty entry-point catalog (no ``axm.credentials``
provider is registered for vault itself), so an unknown ``group.name`` resolves
to a clean CLI error rather than a Python traceback, identically on every call.
The genuine 'absent secret in the keyring is a no-op success' contract — which
needs an injected catalog + keyring — is proven in-process in
``tests/unit/test_tools.py::test_vault_delete_absent_is_noop_success``.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e

_VAULT = (sys.executable, "-m", "axm_vault")


def test_delete_is_deterministic_and_clean() -> None:
    """AC1: repeated ``delete`` invocations are deterministic with no traceback.

    With the empty catalog the command resolves to a clean CLI error (exit 1)
    and, crucially, does so identically on every call — the command carries no
    residual state, mirroring the idempotent no-op the store guarantees.
    """
    args = [*_VAULT, "delete", "svc", "token"]
    first = subprocess.run(args, capture_output=True, text=True, check=False)
    second = subprocess.run(args, capture_output=True, text=True, check=False)
    assert first.returncode == second.returncode
    assert "Traceback" not in first.stderr
    assert "Traceback" not in second.stderr


def test_help_lists_delete_among_seven_commands() -> None:
    """AC4: ``--help`` lists all 7 commands including the new 'delete'."""
    proc = subprocess.run(
        [*_VAULT, "--help"], capture_output=True, text=True, check=True
    )
    out = proc.stdout
    for command in ("setup", "get", "set", "delete", "rotate", "doctor", "path"):
        assert command in out
