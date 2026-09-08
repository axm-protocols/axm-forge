"""E2E subprocess coverage for the lazy CLI dispatch chain (AXM-2023).

Black-box only: no imports of internal symbols. The installed ``axm`` CLI is
driven via :func:`subprocess.run` and assertions are made on stdout / stderr /
exit code. The binary is resolved robustly: the venv console-script is
preferred, falling back to ``python -m axm.cli`` when no script is on PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

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


def test_recursive_alias_cli_preserves_unicode(tmp_path: Path) -> None:
    """AC3: a generated CLI decodes a recursive alias in a subprocess."""
    script = tmp_path / "recursive_alias_cli.py"
    script.write_text(
        """from __future__ import annotations

import cyclopts

from axm.cli import build_command_for_tool
from axm.tools.base import ToolResult

type JsonValue = (
    str
    | int
    | float
    | bool
    | None
    | list[JsonValue]
    | dict[str, JsonValue]
)


class EchoTool:
    def execute(self, *, data: JsonValue) -> ToolResult:
        return ToolResult(success=True, text=data if isinstance(data, str) else "")


app = cyclopts.App()
app.command(build_command_for_tool("echo", EchoTool()))
app()
""",
        encoding="utf-8",
    )
    value = "café naïve résumé 漢字 こんにちは"

    proc = subprocess.run(  # noqa: S603 - trusted interpreter and fixture script
        [sys.executable, str(script), "echo", f'"{value}"'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == value


def test_axm_version_prints_version() -> None:
    """AC4: ``axm --version`` prints the package ``__version__`` and exits 0."""
    proc = _run("--version")
    assert proc.returncode == 0, proc.stderr
    printed = proc.stdout.strip()
    assert _SEMVER.match(printed)
    assert printed == __version__


def test_audit_structured_output_matches_direct_tool_result() -> None:
    """AC2: unified audit JSON preserves the tool contract's score fields."""
    package_root = Path(__file__).parents[2]
    # `axm` is the foundation `axm-audit` consumes, never the reverse: it cannot
    # declare that dependency without inverting the stack. So the audit tool is
    # present in the workspace environment and absent from the package-scoped one
    # CI builds (`uv run --package axm`). The parity this asserts is real wherever
    # the tool exists; where it does not, there is nothing to compare.
    audit_ep = next(
        (ep for ep in entry_points(group="axm.tools") if ep.name == "audit"), None
    )
    if audit_ep is None:
        pytest.skip(
            "axm-audit is not installed here — measured: visible only from the META "
            "venv, neither from the forge workspace venv nor from this "
            "package-scoped one. The generic capability itself is covered by the "
            "unit suite with in-memory tools; what this adds is parity against the "
            "REAL audit tool, which belongs wherever both are installed."
        )
    loaded = audit_ep.load()
    audit_tool = loaded() if isinstance(loaded, type) else loaded
    direct = audit_tool.execute(path=str(package_root), category="lint")

    proc = _run("audit", str(package_root), "--category", "lint", "--json-output")

    assert proc.returncode == 0, proc.stderr
    rendered = json.loads(proc.stdout)
    for key in ("score", "grade", "passed", "failed"):
        assert rendered[key] == direct.data[key]
