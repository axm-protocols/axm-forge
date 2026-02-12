"""Subprocess runner that targets the audited project's venv.

When auditing an external project, tools (ruff, mypy, pytest, etc.) must
execute in *that* project's virtual environment, not axm-audit's own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_in_project(
    cmd: list[str],
    project_path: Path,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command in the target project's environment.

    If the project has a `.venv/`, uses `uv run --directory` to execute
    the command inside that venv. Otherwise falls back to running the
    command directly with `cwd` set to the project path.

    Args:
        cmd: Command and arguments to run.
        project_path: Root of the project being audited.
        **kwargs: Extra arguments forwarded to subprocess.run.

    Returns:
        CompletedProcess result.
    """
    venv_python = project_path / ".venv" / "bin" / "python"

    if venv_python.exists():
        full_cmd = ["uv", "run", "--directory", str(project_path), *cmd]
    else:
        full_cmd = cmd
        kwargs.setdefault("cwd", str(project_path))

    return subprocess.run(full_cmd, **kwargs)  # noqa: S603
