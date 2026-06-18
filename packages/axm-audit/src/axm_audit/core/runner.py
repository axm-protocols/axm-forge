"""Subprocess runner that targets the audited project's venv.

When auditing an external project, tools (ruff, mypy, pytest, etc.) must
execute in *that* project's virtual environment, not axm-audit's own.
"""

from __future__ import annotations

import contextlib
import itertools
import logging
import os
import signal
import subprocess
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: int = 300
"""Default subprocess timeout in seconds (5 minutes)."""

_ENV_FAILURE_RETURNCODES: frozenset[int] = frozenset({2, 124})
"""Exit codes that signal the tool *did not actually run the check*: a
blocking/config error (2) or our timeout sentinel (124).  This is the
single source of truth for the env-failure returncode set, shared by
every subprocess-scored rule (lint, type, and incrementally others)."""


class ProcessVerdict(Enum):
    """Centralized interpretation of a subprocess exit.

    One source of truth for what a returncode *means* to a scored rule,
    so individual rules no longer re-derive returncode semantics
    (which is how an env-failure could silently score a green 100).

    Members:
        CLEAN: the tool ran and found nothing (rc == 0).
        ISSUES: the tool ran and reported findings via an expected
            non-zero exit (e.g. ruff rc=1 with JSON findings).
        ENV_FAILURE: the tool did not actually complete the check
            (rc in :data:`_ENV_FAILURE_RETURNCODES`, or a timeout).
            A scored rule MUST fail loud on this verdict, never green.
    """

    CLEAN = "clean"
    ISSUES = "issues"
    ENV_FAILURE = "env_failure"


def interpret_process(
    result: subprocess.CompletedProcess[str],
) -> ProcessVerdict:
    """Classify a finished subprocess into a :class:`ProcessVerdict`.

    This is the single home of the env-failure returncode set
    (:data:`_ENV_FAILURE_RETURNCODES`). Both the lint and type rules
    route their env-failure decision through here, removing the
    historical mypy-vs-lint asymmetry.

    Args:
        result: The completed (or synthetic-on-timeout) subprocess.

    Returns:
        ``CLEAN`` when ``returncode == 0``; ``ENV_FAILURE`` when the
        returncode is in the env-failure set; otherwise ``ISSUES``
        (an expected non-zero exit carrying findings).
    """
    if result.returncode == 0:
        return ProcessVerdict.CLEAN
    if result.returncode in _ENV_FAILURE_RETURNCODES:
        return ProcessVerdict.ENV_FAILURE
    return ProcessVerdict.ISSUES


_MAX_VENV_SEARCH_DEPTH: int = 5
"""Maximum number of ancestor directories to check when searching for a
``.venv``.  Covers workspace layouts like ``workspace/packages/pkg/``
(3 levels) with margin.  Prevents walking into unrelated directories."""


def find_venv(project_path: Path) -> Path | None:
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


def _process_group_isolation() -> tuple[bool, int]:
    """Return ``(start_new_session, creationflags)`` to isolate the child.

    POSIX: ``start_new_session=True`` runs ``os.setsid`` so the child leads
    a fresh session/process group that ``os.killpg`` can reap wholesale.
    Windows: ``CREATE_NEW_PROCESS_GROUP`` is the closest equivalent. If
    neither primitive is available, fall back to no isolation rather than
    crash (the direct child is still terminated on timeout). Both values
    are accepted by ``Popen`` on every platform (``creationflags=0`` and
    ``start_new_session=False`` are no-ops), so passing them explicitly is
    cross-platform safe.
    """
    if hasattr(os, "setsid"):
        return True, 0
    creation_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return False, int(creation_flag)


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    """Kill ``proc`` and every descendant it forked, best-effort.

    POSIX: ``os.killpg`` SIGKILLs the whole process group created by
    ``start_new_session`` so a wrapper such as ``uv`` and its inner
    ``python`` die together. Windows / no-killpg platforms: fall back to
    killing the direct child. A process that already exited (race) is
    swallowed silently.
    """
    killpg = getattr(os, "killpg", None)
    getpgid = getattr(os, "getpgid", None)
    try:
        if killpg is not None and getpgid is not None:
            killpg(getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        # Group/process already gone, or platform refused the signal:
        # fall back to killing the direct child and ignore if it too is gone.
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            proc.kill()


def run_in_project(  # noqa: PLR0913
    cmd: list[str],
    project_path: Path,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    with_packages: list[str] | None = None,
    capture_output: bool = False,
    text: bool = False,
    check: bool = False,
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
        capture_output: Capture stdout/stderr (piped). Preserves the prior
            ``subprocess.run`` contract.
        text: Decode output as text. Preserves the prior contract.
        check: Raise ``CalledProcessError`` on non-zero exit; a timeout under
            ``check=True`` re-raises ``TimeoutExpired`` instead of returning
            the synthetic rc=124 result.

    Returns:
        CompletedProcess result.  On timeout, returns a synthetic result
        with ``returncode=124`` and the timeout message in ``stderr``.

    Note:
        The child is launched in its own process group / session
        (``start_new_session`` on POSIX, ``CREATE_NEW_PROCESS_GROUP`` on
        Windows). On timeout the **whole group** is killed, so a wrapper
        such as ``uv`` and every process it forked (the inner ``python``,
        worker threads, …) are reaped together instead of being orphaned.
    """
    venv = find_venv(project_path)
    cwd: str | None = None

    if venv is not None:
        with_flags: list[str] = []
        for pkg in with_packages or []:
            with_flags.extend(["--with", pkg])
        full_cmd = ["uv", "run", *with_flags, "--directory", str(project_path), *cmd]
    else:
        full_cmd = cmd
        cwd = str(project_path)

    pipe = subprocess.PIPE if capture_output else None
    new_session, creation_flags = _process_group_isolation()
    proc = subprocess.Popen(  # noqa: S603
        full_cmd,
        stdout=pipe,
        stderr=pipe,
        text=text,
        cwd=cwd,
        start_new_session=new_session,
        creationflags=creation_flags,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        cmd_str = " ".join(full_cmd)
        logger.warning("Command timed out after %ds: %s", timeout, cmd_str)
        _kill_process_group(proc)
        # Drain so no file descriptors or zombie processes are left behind.
        proc.communicate()
        if check:
            # Honor the documented ``check`` contract: a timeout under
            # ``check=True`` must fail loud, never be swallowed into a
            # synthetic rc=124 that a caller could mistake for a result.
            raise
        return subprocess.CompletedProcess(
            args=full_cmd,
            returncode=124,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {cmd_str}",
        )

    result = subprocess.CompletedProcess(
        args=full_cmd, returncode=proc.returncode, stdout=stdout, stderr=stderr
    )
    if check:
        result.check_returncode()
    return result
