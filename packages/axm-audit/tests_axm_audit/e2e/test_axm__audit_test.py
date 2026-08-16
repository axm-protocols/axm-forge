"""Black-box checks for the derived audit_test CLI."""

from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.mark.e2e
def test_audit_test_help_exposes_include_cases_flag() -> None:
    """AC3: the derived CLI advertises the explicit per-case opt-in."""
    axm_bin = shutil.which("axm")
    assert axm_bin is not None

    completed = subprocess.run(  # noqa: S603
        [axm_bin, "audit_test", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    normalized_help = completed.stdout.replace("_", "-")
    assert "--include-cases" in normalized_help
