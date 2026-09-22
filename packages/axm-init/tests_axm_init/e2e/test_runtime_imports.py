"""E2E smoke tests: importing package modules in a fresh interpreter."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap

import pytest


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


def test_paper_template_is_not_bundled() -> None:
    code = (
        "from axm_init.core.templates import TEMPLATES_PKG; "
        "assert not (TEMPLATES_PKG / 'paper-submodule').is_dir()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.e2e
def test_experiment_template_is_not_bundled() -> None:
    code = (
        "from axm_init.core.templates import TEMPLATES_PKG; "
        "assert not (TEMPLATES_PKG / 'experiment' / 'copier.yml').is_file()"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tempfile.gettempdir(),
    )
    assert result.returncode == 0, result.stderr


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
