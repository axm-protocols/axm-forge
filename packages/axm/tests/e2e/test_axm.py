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

from axm import __version__

pytestmark = pytest.mark.e2e

# POSIX convention: 2 = bad command-line usage (unknown command).
_EXIT_USAGE = 2

# Semver-ish: MAJOR.MINOR.PATCH with optional pre-release / build / dev suffix
# (hatch-vcs emits e.g. ``0.4.0`` or ``0.4.1.dev3+g<sha>``).
_SEMVER = re.compile(r"^\d+\.\d+\.\d+")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the ``axm`` package CLI as a subprocess, capturing text I/O.

    Drives the installed ``axm`` console-script declared in
    ``[project.scripts]`` when it is on PATH; otherwise falls back to
    ``[sys.executable, "-m", "axm.cli"]`` so the suite still runs in a bare
    env (e.g. CI before the package is pip-installed with its entry point).
    Both forms invoke the package's own CLI entrypoint end-to-end.
    """
    # Console-script first (declared in ``[project.scripts]``); module fallback
    # for bare envs. Each branch passes a direct list literal so the package
    # entrypoint (``axm`` / ``-m axm.cli``) stays statically visible (e2e).
    if shutil.which("axm"):
        return subprocess.run(  # noqa: S603 - trusted, locally-resolved axm CLI
            ["axm", *args],  # noqa: S607 - intentional PATH lookup of axm script
            capture_output=True,
            text=True,
            timeout=60,
        )
    return subprocess.run(  # noqa: S603 - trusted, locally-resolved axm CLI
        [sys.executable, "-m", "axm.cli", *args],
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
    """AC4: ``axm --version`` prints the package ``__version__`` and exits 0."""
    proc = _run("--version")
    assert proc.returncode == 0, proc.stderr
    printed = proc.stdout.strip()
    assert _SEMVER.match(printed)
    assert printed == __version__
