"""Subprocess runner that targets the audited project's venv.

When auditing an external project, tools (ruff, mypy, pytest, etc.) must
execute in *that* project's virtual environment, not axm-audit's own.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: int = 300
"""Default subprocess timeout in seconds (5 minutes)."""


def run_in_project(
    cmd: list[str],
    project_path: Path,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command in the target project's environment.

    If the project has a ``.venv/``, uses ``uv run --directory`` to execute
    the command inside that venv. Otherwise falls back to running the
    command directly with ``cwd`` set to the project path.

    Args:
        cmd: Command and arguments to run.
        project_path: Root of the project being audited.
        timeout: Maximum seconds to wait before killing the subprocess.
            Defaults to 300 (5 minutes).
        **kwargs: Extra arguments forwarded to ``subprocess.run``.

    Returns:
        CompletedProcess result.  On timeout, returns a synthetic result
        with ``returncode=124`` and the timeout message in ``stderr``.
    """
    venv_python = project_path / ".venv" / "bin" / "python"

    if venv_python.exists():
        full_cmd = ["uv", "run", "--directory", str(project_path), *cmd]
    else:
        full_cmd = cmd
        kwargs.setdefault("cwd", str(project_path))

    try:
        return subprocess.run(full_cmd, timeout=timeout, **kwargs)  # noqa: S603
    except subprocess.TimeoutExpired:
        cmd_str = " ".join(full_cmd)
        logger.warning("Command timed out after %ds: %s", timeout, cmd_str)
        return subprocess.CompletedProcess(
            args=full_cmd,
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {cmd_str}",
        )
