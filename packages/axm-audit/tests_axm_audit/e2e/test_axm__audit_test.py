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

    help_by_tool: dict[str, str] = {}
    for tool_name in ("audit", "audit_test", "audit_fix", "doc_gate"):
        completed = subprocess.run(  # noqa: S603
            [axm_bin, tool_name, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        help_by_tool[tool_name] = completed.stdout

    normalized_help = help_by_tool["audit_test"].replace("_", "-")
    assert "--include-cases" in normalized_help
