"""RunCommandTool — execute shell commands with timeout and output truncation.

Registered as ``run_command`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.engine import _resolve_safe

__all__ = ["RunCommandTool"]

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30
_MAX_OUTPUT_CHARS = 4096

# Patterns that should never be executed.
_BLOCKED_PATTERNS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf /*",
    "sudo ",
    "mkfs",
    "dd if=",
    ":(){",
    "> /dev/sd",
    "chmod -R 777 /",
    "mv / ",
)


def _is_blocked(command: str) -> bool:
    """Return True if *command* contains a blocked pattern."""
    lower = command.lower().strip()
    return any(pat in lower for pat in _BLOCKED_PATTERNS)


def _truncate(output: str) -> tuple[str, bool]:
    """Truncate output to ``_MAX_OUTPUT_CHARS``.

    Returns ``(text, was_truncated)``.
    """
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output, False
    return output[:_MAX_OUTPUT_CHARS] + "\n[truncated]", True


def render_text(
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
    timed_out: bool,
    truncated: bool,
) -> str:
    """Render a compact LLM-facing view of a command result.

    The header carries the exit code (with a ``✗`` marker when non-zero so a
    failure is impossible to miss) plus explicit ``timeout`` / ``truncated``
    flags. ``stdout`` and ``stderr`` are embedded **raw** (not JSON-escaped),
    each under its own labelled section, so no output is ever lost relative to
    ``data`` — only the structural JSON noise is dropped.
    """
    flags = [f"exit {exit_code}"]
    if exit_code != 0 or timed_out:
        flags[0] += " ✗"
    if timed_out:
        flags.append("timeout")
    if truncated:
        flags.append("truncated")
    header = "run_command | " + " · ".join(flags)

    sections = [header]
    if stdout:
        sections.append("stdout:\n" + stdout.rstrip("\n"))
    if stderr:
        sections.append("stderr:\n" + stderr.rstrip("\n"))
    if not stdout and not stderr:
        sections.append("(no output)")
    return "\n".join(sections)


class RunCommandTool:
    """Execute **arbitrary shell commands** with timeout and output truncation.

    Runs the given command via ``subprocess.run`` in the resolved working
    directory, with configurable timeout and output size caps. The command
    string is executed verbatim by the shell, so this tool can run *any*
    shell command the calling process is permitted to run.

    .. warning::
        The ``_BLOCKED_PATTERNS`` denylist is a **best-effort guardrail**
        against obvious footguns (e.g. ``rm -rf /``), **not** a security
        sandbox. It matches substrings and is **bypassable by design**
        (encoding, indirection, equivalent commands). Do not rely on it for
        isolation or to contain untrusted input — treat any command passed
        here as executing with the full privileges of the host process.

    Registered as ``run_command`` via axm.tools entry point.
    """

    agent_hint: str = (
        "Runs ARBITRARY shell commands in cwd with host privileges."
        " The blocked-command denylist is a best-effort guardrail against"
        " obvious footguns, NOT a security sandbox, and is bypassable by"
        " design. No cd/pipes/&&. Returns stdout+stderr truncated to 4K"
        " chars. Use for tests, builds, scripts."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "run_command"

    def execute(
        self,
        *,
        command: str | None = None,
        path: str = ".",
        cwd: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
        **kwargs: object,
    ) -> ToolResult:
        """Execute a shell command.

        Args:
            command: Shell command string (required).
            path: Project root directory (default ".").
            cwd: Working directory, relative to root (optional).
            timeout: Timeout in seconds (default 30).

        Returns:
            ToolResult with stdout, stderr, exit_code, and timed_out.
        """
        root_str = path
        cwd_rel = cwd

        # ── Validate inputs ──────────────────────────────────────────
        if not command or not command.strip():
            return ToolResult(
                success=False,
                error="Missing required argument: command",
            )

        if _is_blocked(command):
            return ToolResult(
                success=False,
                error="Blocked command: this command is not allowed",
            )

        root = Path(root_str).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False,
                error=f"Root is not a directory: {root_str}",
            )

        # Resolve cwd within the sandbox
        if cwd_rel:
            resolved_cwd = _resolve_safe(root, cwd_rel)
            if resolved_cwd is None:
                return ToolResult(
                    success=False,
                    error=f"cwd escapes project root: {cwd_rel}",
                )
            if not resolved_cwd.is_dir():
                return ToolResult(
                    success=False,
                    error=f"cwd is not a directory: {cwd_rel}",
                )
            work_dir = resolved_cwd
        else:
            work_dir = root

        # ── Execute ──────────────────────────────────────────────────
        return _run(command, work_dir, timeout)


def _run(command: str, work_dir: Path, timeout: int) -> ToolResult:
    """Run the command and return a ToolResult."""
    timed_out = False
    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = str(exc.stdout) if exc.stdout else ""
        stderr = str(exc.stderr) if exc.stderr else ""
        exit_code = -1
    except FileNotFoundError:
        return ToolResult(
            success=False,
            error=f"Command not found: {shlex.split(command)[0]}",
        )
    except (OSError, ValueError) as exc:
        return ToolResult(success=False, error=str(exc))

    stdout_trunc, stdout_was = _truncate(str(stdout))
    stderr_trunc, stderr_was = _truncate(str(stderr))

    truncated = stdout_was or stderr_was
    return ToolResult(
        success=True,
        data={
            "stdout": stdout_trunc,
            "stderr": stderr_trunc,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": truncated,
        },
        text=render_text(
            stdout=stdout_trunc,
            stderr=stderr_trunc,
            exit_code=exit_code,
            timed_out=timed_out,
            truncated=truncated,
        ),
    )
