"""E2E black-box tests for the ``axm-vault`` CLI (subprocess).

Note on never-leak: the value-free doctor invariant (a plaintext secret never
enters the provenance report) is verified where it can actually *fail* — the
in-process ``test_doctor_never_returns_value`` in ``tests/unit/test_doctor.py``,
which injects a catalog + a keyring secret and asserts the value is absent from
the serialized report. A subprocess ``doctor`` here cannot prove that: it sees
the real, empty entry-point catalog (no ``axm.credentials`` provider is
registered) and a different OS keyring than the test process, so it prints
nothing regardless of implementation — an assertion on its stdout would be
vacuous. The e2e layer instead asserts the observable black-box contract:
``doctor`` exits 0 and emits nothing on the empty-catalog nominal path.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e

_VAULT = (sys.executable, "-m", "axm_vault")


def test_path_prints_home() -> None:
    """AC4: ``axm-vault path`` prints the ~/.axm home directory."""
    proc = subprocess.run([*_VAULT, "path"], capture_output=True, text=True, check=True)
    assert proc.stdout.strip().endswith("/.axm")


def test_doctor_empty_catalog_exits_clean() -> None:
    """AC4: ``axm-vault doctor`` on the empty catalog exits 0 and prints nothing.

    This is the honest black-box claim (see the module note): with no
    ``axm.credentials`` provider registered, the doctor has nothing to report
    and must still exit cleanly.
    """
    proc = subprocess.run(
        [*_VAULT, "doctor"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_help_lists_commands_no_import() -> None:
    """AC4: ``--help`` lists the 6 commands and never advertises 'import'."""
    proc = subprocess.run(
        [*_VAULT, "--help"], capture_output=True, text=True, check=True
    )
    out = proc.stdout
    for command in ("setup", "get", "set", "rotate", "doctor", "path"):
        assert command in out
    assert "import" not in out
