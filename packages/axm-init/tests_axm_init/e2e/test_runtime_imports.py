"""E2E smoke tests: importing package modules in a fresh interpreter."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_copier_imports_at_runtime() -> None:
    """Importing copier adapter in a fresh interpreter raises no ImportError."""
    code = textwrap.dedent("""
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        print("OK")
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ImportError: {result.stderr}"
    assert "OK" in result.stdout


def test_checker_imports_at_runtime() -> None:
    """Importing checker in a fresh interpreter raises no ImportError."""
    code = textwrap.dedent("""
        from axm_init.core.checker import CheckEngine
        print("OK")
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"ImportError: {result.stderr}"
    assert "OK" in result.stdout
