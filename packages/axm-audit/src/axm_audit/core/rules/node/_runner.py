"""Node-ecosystem subprocess runner — the npx pendant of ``core.runner``.

``core.runner.run_in_project`` is uv/Python-centric (it shells out through
``uv run``). Node rules need the same guarantees — process-group isolation,
timeout-kills-the-group, env-failure classification — but routed through the
project's local ``node_modules/.bin`` (preferred) or ``npx`` (fallback).

This module reuses the env-failure verdict semantics from ``core.runner`` so a
tool that fails to *run* never scores a green result.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from axm_audit.core.runner import (
    ProcessVerdict,
    _kill_process_group,
    _process_group_isolation,
    interpret_process,
)

__all__ = [
    "ProcessVerdict",
    "interpret_process",
    "node_tool_available",
    "path_tool_available",
    "run_node_tool",
]

_DEFAULT_TIMEOUT = 300


def node_tool_available(project_path: Path, binary: str) -> bool:
    """Return True if *binary* is actually installed for *project_path*.

    A tool counts as available only if it resolves to a real executable in the
    project's local ``node_modules/.bin``. A bare ``npx`` on PATH is **not**
    enough: ``npx --no-install`` of an uninstalled tool exits non-zero with no
    output, which a scorer would otherwise mistake for "ran clean, zero issues"
    (a false green). A serious project installs its lint/type toolchain in its
    devDependencies, so requiring the local binary is the correct contract.
    """
    local = project_path / "node_modules" / ".bin" / binary
    return local.is_file()


def path_tool_available(binary: str) -> bool:
    """Return True if *binary* resolves on the system PATH.

    For tools that are not project-local node_modules binaries but global CLIs:
    ``npm`` (for ``npm audit``) and ``gitleaks`` (a system install).
    """
    return shutil.which(binary) is not None


def _resolve_cmd(
    project_path: Path, binary: str, args: list[str], *, on_path: bool
) -> list[str]:
    """Build the argv to invoke *binary*.

    ``on_path`` selects a global PATH command (npm, gitleaks); otherwise the
    project-local ``node_modules/.bin`` binary. ``npx`` is intentionally not a
    fallback for local binaries (it produces false-green env failures).
    """
    if on_path:
        return [binary, *args]
    local = project_path / "node_modules" / ".bin" / binary
    if local.is_file():
        return [str(local), *args]
    return ["npx", "--no-install", binary, *args]


def run_node_tool(
    binary: str,
    args: list[str],
    project_path: Path,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    on_path: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a Node CLI tool in *project_path* with process-group isolation.

    Mirrors :func:`axm_audit.core.runner.run_in_project`: the child runs in its
    own process group and, on timeout, the whole group is killed and a synthetic
    ``returncode=124`` result is returned so the caller can route it through
    :func:`interpret_process` as an ``ENV_FAILURE``.

    Args:
        binary: Node CLI binary name (e.g. ``"eslint"``).
        args: Arguments to pass to the binary.
        project_path: Project root (cwd for the subprocess).
        timeout: Maximum seconds before the process group is killed.

    Returns:
        The completed process (stdout/stderr captured as text).
    """
    full_cmd = _resolve_cmd(project_path, binary, args, on_path=on_path)
    new_session, creation_flags = _process_group_isolation()
    proc = subprocess.Popen(  # noqa: S603
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(project_path),
        start_new_session=new_session,
        creationflags=creation_flags,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        proc.communicate()
        return subprocess.CompletedProcess(
            args=full_cmd,
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
        )
    return subprocess.CompletedProcess(
        args=full_cmd, returncode=proc.returncode, stdout=stdout, stderr=stderr
    )
