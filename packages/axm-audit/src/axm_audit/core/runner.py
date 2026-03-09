"""Subprocess runner that targets the audited project's venv.

When auditing an external project, tools (ruff, mypy, pytest, etc.) must
execute in *that* project's virtual environment, not axm-audit's own.
"""

from __future__ import annotations

import itertools
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: int = 300
"""Default subprocess timeout in seconds (5 minutes)."""

_MAX_VENV_SEARCH_DEPTH: int = 5
"""Maximum number of ancestor directories to check when searching for a
``.venv``.  Covers workspace layouts like ``workspace/packages/pkg/``
(3 levels) with margin.  Prevents walking into unrelated directories."""


def _find_venv(project_path: Path) -> Path | None:
    """Locate the nearest ``.venv`` directory for a project.

    Checks ``project_path`` first, then walks up the directory tree to
    support **uv monorepo workspaces** where the shared ``.venv`` lives
    at the workspace root rather than inside the individual package.

    The search is bounded to :data:`_MAX_VENV_SEARCH_DEPTH` levels to
    avoid accidentally picking up an unrelated ``.venv`` higher in the
    file system.

    Args:
        project_path: Root of the project being audited.

    Returns:
        The ``.venv`` directory if found, or ``None`` if no virtual
        environment exists in the project or any of its ancestors
        (within the bounded depth).
    """
    current = project_path.resolve()
    # Walk up at most _MAX_VENV_SEARCH_DEPTH levels
    for directory in itertools.islice(
        (current, *current.parents), _MAX_VENV_SEARCH_DEPTH
    ):
        venv_python = directory / ".venv" / "bin" / "python"
        if venv_python.exists():
            return directory / ".venv"
    return None


def run_in_project(
    cmd: list[str],
    project_path: Path,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    with_packages: list[str] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command in the target project's environment.

    Locates the nearest ``.venv/`` — either in ``project_path`` itself
    or in an ancestor directory (for uv monorepo workspace members).
    Uses ``uv run --directory`` to execute the command within the
    correct environment.  Falls back to running the command directly
    with ``cwd`` set when no virtual environment is found.

    Args:
        cmd: Command and arguments to run.
        project_path: Root of the project being audited.
        timeout: Maximum seconds to wait before killing the subprocess.
            Defaults to 300 (5 minutes).
        with_packages: Optional packages to inject at runtime via
            ``uv run --with <pkg>``.  Only effective when a ``.venv/``
            is found (i.e. when ``uv run`` is used).  Allows audit tools
            to be available in the target project without requiring
            them as declared dependencies.
        **kwargs: Extra arguments forwarded to ``subprocess.run``.

    Returns:
        CompletedProcess result.  On timeout, returns a synthetic result
        with ``returncode=124`` and the timeout message in ``stderr``.
    """
    venv = _find_venv(project_path)

    if venv is not None:
        with_flags: list[str] = []
        for pkg in with_packages or []:
            with_flags.extend(["--with", pkg])
        full_cmd = ["uv", "run", *with_flags, "--directory", str(project_path), *cmd]
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
