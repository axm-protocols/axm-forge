"""Install plans: propose an official install command, run only on confirm.

This module NEVER installs silently. ``install_command`` only *describes* the
official command for a known tool; ``run_install`` executes it strictly when
the caller opts in with ``confirm=True``. The default path is a dry-run that
echoes the command it *would* run — honouring the
no-system-install-without-authorization posture.
"""

from __future__ import annotations

import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel

from axm_doctor.detect import ToolStatus, detect_tool

__all__ = [
    "InstallPlan",
    "InstallResult",
    "install_command",
    "run_install",
]

# Conventional shell code for "command not found / could not execute" — used
# as the failure returncode when an installer is unreachable or its binary is
# missing, so callers see a non-zero state instead of a traceback.
_UNAVAILABLE_RC = 127
# Wall-clock cap on the installer-script download (controlled internal URL).
_DOWNLOAD_TIMEOUT_S = 30
# Only a 200 response carries the installer script; anything else is an error
# page that must never be executed.
_HTTP_OK = 200


class InstallPlan(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """A proposed install command for a single tool — description only.

    Building a plan runs nothing. ``argv`` is the program + arguments executed
    as a bare exec (NO shell). ``fetch_url``, when set, marks a script-installer
    plan (e.g. the uv ``curl | sh`` recipe): instead of a shell pipe, the script
    is downloaded to a temp file and run as ``sh <tmpfile>`` — both steps are
    argv execs, never ``shell=True``. ``human_command`` is the copy-pasteable
    form a human would type.
    """

    tool: str
    argv: list[str]
    human_command: str
    fetch_url: str | None = None


class InstallResult(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Outcome of :func:`run_install`.

    On a dry-run (``confirm=False``) ``executed`` is False, ``returncode`` is
    None, and ``post_check`` is None — nothing was installed, so nothing is
    re-detected. On a confirmed run, ``post_check`` carries the re-detected
    :class:`~axm_doctor.detect.ToolStatus`.
    """

    command: str
    executed: bool
    returncode: int | None = None
    post_check: ToolStatus | None = None


# Registry of official install commands, keyed by tool name. The uv installer
# is the documented ``curl | sh`` recipe; rather than a shell pipe we model it
# as a two-step argv pipeline via ``fetch_url`` (download the script, then run
# ``sh <tmpfile>``) so NO branch ever needs ``shell=True``. The npm tools are
# plain argv lists.
_UV_INSTALL_URL = "https://astral.sh/uv/install.sh"

_REGISTRY: dict[str, InstallPlan] = {
    "uv": InstallPlan(
        tool="uv",
        argv=["curl", "-LsSf", _UV_INSTALL_URL],
        human_command=f"curl -LsSf {_UV_INSTALL_URL} | sh",
        fetch_url=_UV_INSTALL_URL,
    ),
    "claude": InstallPlan(
        tool="claude",
        argv=["npm", "i", "-g", "@anthropic-ai/claude-code"],
        human_command="npm i -g @anthropic-ai/claude-code",
    ),
    "codex": InstallPlan(
        tool="codex",
        argv=["npm", "i", "-g", "@openai/codex"],
        human_command="npm i -g @openai/codex",
    ),
}


def install_command(tool: str) -> InstallPlan | None:
    """Return the official :class:`InstallPlan` for ``tool``, or None.

    Runs nothing. An unknown tool returns None rather than guessing a
    command.
    """
    return _REGISTRY.get(tool)


def run_install(plan: InstallPlan, *, confirm: bool = False) -> InstallResult:
    """Execute ``plan`` only when ``confirm is True``; otherwise dry-run.

    With the default ``confirm=False`` this NEVER installs: it returns the
    command it *would* run with ``executed=False`` and ``returncode=None``.
    With ``confirm=True`` it runs the command, then re-detects the tool via
    :func:`~axm_doctor.detect.detect_tool` and reports the post-install state.
    """
    if not confirm:
        return InstallResult(command=plan.human_command, executed=False)

    returncode = _run_fetch_install(plan) if plan.fetch_url else _run_argv(plan.argv)
    return InstallResult(
        command=plan.human_command,
        executed=True,
        returncode=returncode,
        post_check=detect_tool(plan.tool),
    )


def _run_argv(argv: list[str]) -> int:
    """Run a controlled argv list with no shell and return its returncode.

    A missing binary (``OSError``/``FileNotFoundError``) is reported as the
    ``_UNAVAILABLE_RC`` non-zero returncode rather than propagating a traceback,
    so the caller gets a clean failed :class:`InstallResult`.
    """
    try:
        completed = subprocess.run(argv, shell=False, check=False)  # noqa: S603
    except OSError:
        return _UNAVAILABLE_RC
    return completed.returncode


def _run_fetch_install(plan: InstallPlan) -> int:
    """Download a script installer to a temp file and run ``sh <tmpfile>``.

    Replaces the legacy ``curl | sh`` shell pipe: the script is fetched over
    HTTPS to a temporary file, executed via a bare ``sh <tmpfile>`` argv (no
    shell interpolation), then the temp file is removed. ``plan.fetch_url`` is
    a controlled internal constant, never user input.
    """
    if plan.fetch_url is None:  # pragma: no cover - guarded by caller
        raise ValueError("fetch install requires a fetch_url")
    # NOTE: the URL is a controlled internal constant, but its *content* is a
    # remote script with no checksum — the sha256-pin hardening is a separate
    # future ticket, out of scope here.
    try:
        with urllib.request.urlopen(  # noqa: S310
            plan.fetch_url, timeout=_DOWNLOAD_TIMEOUT_S
        ) as response:
            # A non-200 body is an error page (404/503/...), NOT an installer
            # script: never write it to a temp file and run `sh <tmpfile>`.
            if response.status != _HTTP_OK:
                return _UNAVAILABLE_RC
            script = response.read()
    except (urllib.error.URLError, OSError):
        return _UNAVAILABLE_RC
    # NamedTemporaryFile closes the fd on context exit (no descriptor leak);
    # delete=False keeps the path alive for the `sh <tmpfile>` exec, and the
    # finally unlinks it even when the install fails.
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as handle:
        handle.write(script)
        tmp = Path(handle.name)
    try:
        return _run_argv(["sh", str(tmp)])
    finally:
        tmp.unlink(missing_ok=True)
