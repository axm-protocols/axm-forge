from __future__ import annotations

import subprocess

import pytest


@pytest.mark.e2e
def test_cli_audit_category_test_quality_exit_0() -> None:
    """CLI `axm-audit audit . --category test_quality` exits 0 and emits output."""
    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", ".", "--category", "test_quality"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout != ""
