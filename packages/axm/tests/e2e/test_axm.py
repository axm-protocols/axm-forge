"""E2E subprocess coverage for the lazy CLI dispatch chain (AXM-2023).

Black-box only: no imports of internal symbols. The installed ``axm`` CLI is
driven via :func:`subprocess.run` and assertions are made on stdout / stderr /
exit code. The binary is resolved robustly: the venv console-script is
preferred, falling back to ``python -m axm.cli`` when no script is on PATH.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from importlib.metadata import entry_points

import pytest

pytestmark = pytest.mark.e2e

# POSIX convention: 2 = bad command-line usage (unknown command).
_EXIT_USAGE = 2

# Semver-ish: MAJOR.MINOR.PATCH with optional pre-release / build / dev suffix
# (hatch-vcs emits e.g. ``0.4.0`` or ``0.4.1.dev3+g<sha>``).
_SEMVER = re.compile(r"^\d+\.\d+\.\d+")


def _axm_argv() -> list[str]:
    """Resolve the ``axm`` invocation: console-script if on PATH, else module.

    Prefers the venv console-script (``axm``); falls back to
    ``[sys.executable, "-m", "axm.cli"]`` so the suite runs in a bare env
    (e.g. CI before the package is pip-installed with its entry point).
    """
    script = shutil.which("axm")
    if script:
        return [script]
    return [sys.executable, "-m", "axm.cli"]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the resolved ``axm`` binary with ``args``, capturing text I/O."""
    return subprocess.run(  # noqa: S603 - trusted, locally-resolved axm binary
        [*_axm_argv(), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _live_tool_name() -> str | None:
    """Discover one really-installed ``axm.tools`` entry-point name, or None."""
    eps = entry_points(group="axm.tools")
    return next(iter(sorted(ep.name for ep in eps)), None)


def test_axm_no_args_prints_catalog() -> None:
    """AC1: ``axm`` with no args prints the catalog and exits 0."""
    proc = _run()
    assert proc.returncode == 0, proc.stderr
    # Catalog is non-empty and free of a Python traceback.
    assert proc.stdout.strip()
    assert "Traceback (most recent call last)" not in proc.stderr


def test_axm_tool_help_renders() -> None:
    """AC2: ``axm <live_tool> --help`` renders help end-to-end, exits 0.

    Proves the entry-point -> cyclopts -> ``get_type_hints`` chain works on a
    really-installed tool. Skips gracefully if no ``axm.tools`` is installed.
    """
    tool = _live_tool_name()
    if tool is None:
        pytest.skip("no axm.tools entry points installed in this environment")
    proc = _run(tool, "--help")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()
    assert "Traceback (most recent call last)" not in proc.stderr


def test_axm_unknown_command_exits_2() -> None:
    """AC3: ``axm nope`` exits 2 with ``Unknown command`` on stderr."""
    proc = _run("nope")
    assert proc.returncode == _EXIT_USAGE
    assert "Unknown command" in proc.stderr


def test_axm_version_prints_version() -> None:
    """AC4: ``axm --version`` prints a semver on stdout and exits 0."""
    proc = _run("--version")
    assert proc.returncode == 0, proc.stderr
    assert _SEMVER.match(proc.stdout.strip())
