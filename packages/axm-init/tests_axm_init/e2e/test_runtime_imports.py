"""E2E smoke tests: importing package modules in a fresh interpreter."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

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


@pytest.mark.e2e
def test_paper_template_ships_with_distribution() -> None:
    # AC1: a fresh interpreter outside the source tree resolves the paper
    # template from the installed distribution, copier config included.
    code = textwrap.dedent("""
        from pathlib import Path

        from axm_init.core.templates import TemplateType, get_template_path

        path = Path(get_template_path(TemplateType.PAPER))
        assert path.is_dir(), f"not a directory: {path}"
        assert (path / "copier.yml").is_file(), f"no copier.yml in {path}"
        print(path)
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tempfile.gettempdir(),
    )
    assert result.returncode == 0, result.stderr
    printed = Path(result.stdout.strip())
    assert printed.is_dir(), result.stdout
    assert (printed / "copier.yml").is_file()


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
