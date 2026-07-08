"""Stdlib-only detection of external tools and third-party auth state.

Tool/auth probing (:func:`detect_tool`, :func:`detect_auth`) depends on the
standard library and pydantic only — no AXM package is imported at module
load, so this layer runs as the bootstrap probe *before* the rest of AXM is
installable. The git-identity check (:func:`detect_git_identity`) additionally
resolves the central ``axm-config`` store (``[git].default``) to know whether a
committer identity exists; that import is deferred to the function body so the
module stays importable on a machine where ``axm-config`` is not yet present.
The value is never read, only its presence. All detection is strictly
read-only: it inspects an exit code or the *existence* of a credential/store
entry, and never reads the token or identity value.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

__all__ = [
    "AuthState",
    "AuthStatus",
    "GhConfigState",
    "GhConfigStatus",
    "GitIdentityState",
    "GitIdentityStatus",
    "ToolState",
    "ToolStatus",
    "detect_auth",
    "detect_gh_config",
    "detect_git_identity",
    "detect_tool",
]

type ToolState = Literal["present", "absent"]
type AuthState = Literal["logged_in", "logged_out", "not_installed"]
type GitIdentityState = Literal["configured", "unconfigured"]
type GhConfigState = Literal["configured", "unconfigured", "not_installed"]

_VERSION_TIMEOUT_S = 5

# Per-tool auth wiring. ``cred`` is the credential file relative to ``~`` whose
# *existence* (never content) signals logged-in for credential-file tools.
_CRED_FILES: dict[str, str] = {
    "claude": ".claude/.credentials.json",
    "codex": ".codex/auth.json",
}
_LOGIN_CMDS: dict[str, str] = {
    "gh": "gh auth login",
    "claude": "claude login",
    "codex": "codex login",
}
# macOS-only auth wiring. On Darwin the token lives in the login Keychain, not
# in a credential file under ``~`` — the generic-password *service* name whose
# existence (exit code, never value) signals logged-in.
_KEYCHAIN_SERVICES: dict[str, str] = {"claude": "Claude Code-credentials"}


class ToolStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen result of probing a single external tool on ``PATH``."""

    name: str
    state: ToolState
    version: str | None = None
    path: str | None = None


class AuthStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen read-only auth state for a third-party binary.

    Carries the command to recover from ``logged_out`` (``login_cmd``) but
    NEVER a token value — detection is existence/exit-code only.
    """

    tool: str
    state: AuthState
    login_cmd: str | None = None


def detect_tool(name: str) -> ToolStatus:
    """Probe ``name`` on ``PATH`` and parse ``<name> --version``.

    Returns ``present`` with the parsed version string when found, ``absent``
    otherwise. Never raises on a missing or misbehaving tool.
    """
    path = shutil.which(name)
    if path is None:
        return ToolStatus(name=name, state="absent")
    return ToolStatus(
        name=name,
        state="present",
        version=_probe_version(name),
        path=path,
    )


def detect_auth(tool: str) -> AuthStatus:
    """Report read-only auth state for a third-party binary.

    ``gh`` is probed via the exit code of ``gh auth status``; credential-file
    tools (``claude``, ``codex``) via the *existence* of their credential file
    under ``~`` — the file is never opened, so no token is ever read.
    """
    login_cmd = _LOGIN_CMDS.get(tool)
    if tool == "gh":
        state = _detect_gh_auth()
    elif tool in _CRED_FILES:
        # On darwin the token may live in the login Keychain; check it first,
        # then fall back to the credential file. Either source present ->
        # logged_in, so a file-backed session (container, CI, CLAUDE_CONFIG_DIR,
        # a locked/absent Keychain) is never mis-reported as logged_out.
        keychain_ok = (
            sys.platform == "darwin"
            and tool in _KEYCHAIN_SERVICES
            and _detect_keychain_auth(_KEYCHAIN_SERVICES[tool]) == "logged_in"
        )
        state = "logged_in" if keychain_ok or _cred_file_present(tool) else "logged_out"
    else:
        # Unknown auth tool: when its binary IS on PATH, "not_installed" would
        # be misleading — we simply cannot verify its login, so report
        # logged_out (recovery hint follows if known). Only when the binary is
        # absent is "not_installed" the honest state.
        state = "logged_out" if shutil.which(tool) is not None else "not_installed"
    return AuthStatus(
        tool=tool,
        state=state,
        login_cmd=login_cmd if state == "logged_out" else None,
    )


def _cred_file_present(tool: str) -> bool:
    """True when ``tool``'s credential file exists and is non-empty.

    A 0-byte credential file carries no token: existence alone is not a login.
    The file is stat'd, never opened, so no secret transits.
    """
    cred = Path.home() / _CRED_FILES[tool]
    return cred.is_file() and cred.stat().st_size > 0


def _probe_version(name: str) -> str | None:
    """Return a dotted version parsed from ``<name> --version``, or ``None``.

    Extracts the LAST dotted number in the output (so a banner like
    ``Python 3.12 wrapper, tool 2.1.0`` yields ``2.1.0``, not the interpreter
    partial); falls back to the first line only when no dotted number is
    present. ``None`` when the tool cannot be run.
    """
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = proc.stdout.strip() or proc.stderr.strip()
    if not raw:
        return None
    # Extract a dotted version (e.g. "1.2.3") from possibly-noisy output rather
    # than leaking a whole banner. Use the LAST match, not the first: a banner
    # like "Python 3.12 wrapper, tool 2.1.0" must yield the tool's own version
    # (2.1.0), not the leading interpreter partial (3.12). Fall back to the
    # first line if no dotted number is present.
    matches: list[str] = re.findall(r"\d+\.\d+(?:\.\d+)?", raw)
    if matches:
        return matches[-1]
    return raw.splitlines()[0].strip()


class GitIdentityStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen verdict on whether a git committer identity is resolvable.

    ``state`` is decided from the *presence* of a ``[git].default`` store entry
    or the exit code of ``git config --get user.email`` — the identity value
    itself is never read.
    """

    state: GitIdentityState


class GhConfigStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen verdict on whether ``gh`` carries a base configuration.

    ``configured`` when ``gh config get git_protocol`` exits 0, ``unconfigured``
    otherwise, ``not_installed`` when the ``gh`` binary is absent. The config
    value itself is never read.
    """

    state: GhConfigState


def detect_git_identity() -> GitIdentityStatus:
    """Report whether a git committer identity is resolvable, value-free.

    Cheapest source first: a truthy ``[git].default`` in the ``axm-config``
    store means an identity exists. Otherwise fall back to the exit code of
    ``git config --get user.email`` (its stdout — the email — is captured and
    discarded, never returned). Any missing binary / ``OSError`` /
    ``SubprocessError`` degrades to ``unconfigured`` without raising.
    """
    import axm_config

    if axm_config.get("git", "default", default=None):
        return GitIdentityStatus(state="configured")
    if shutil.which("git") is None:
        return GitIdentityStatus(state="unconfigured")
    try:
        proc = subprocess.run(
            ["git", "config", "--get", "user.email"],  # noqa: S607 - controlled binary
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return GitIdentityStatus(state="unconfigured")
    state: GitIdentityState = "configured" if proc.returncode == 0 else "unconfigured"
    return GitIdentityStatus(state=state)


def detect_gh_config() -> GhConfigStatus:
    """Report whether ``gh`` carries a base config, value-free.

    Probes the exit code of ``gh config get git_protocol`` (its stdout is
    captured and discarded). ``gh`` absent → ``not_installed``; any
    ``OSError`` / ``SubprocessError`` degrades to ``unconfigured``. This is
    distinct from and additional to the ``gh auth status`` login check.
    """
    if shutil.which("gh") is None:
        return GhConfigStatus(state="not_installed")
    try:
        proc = subprocess.run(
            ["gh", "config", "get", "git_protocol"],  # noqa: S607 - controlled binary
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return GhConfigStatus(state="unconfigured")
    state: GhConfigState = "configured" if proc.returncode == 0 else "unconfigured"
    return GhConfigStatus(state=state)


def _detect_gh_auth() -> AuthState:
    """Probe ``gh auth status`` exit code without reading any token."""
    if shutil.which("gh") is None:
        return "not_installed"
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],  # noqa: S607 - gh is a controlled, known binary
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "logged_out"
    return "logged_in" if proc.returncode == 0 else "logged_out"


def _detect_keychain_auth(service: str) -> AuthState:
    """Probe the macOS login Keychain for ``service`` without reading the token.

    Mirrors :func:`_detect_gh_auth`: only the exit code of
    ``security find-generic-password -s <service>`` is inspected
    (``capture_output=True`` keeps any matched blob off the terminal), so the
    secret value never transits. A missing ``security`` binary or any
    OS/subprocess error degrades to ``logged_out`` rather than raising.
    """
    if shutil.which("security") is None:
        return "logged_out"
    try:
        proc = subprocess.run(  # noqa: S603 - service is a hardcoded literal from _KEYCHAIN_SERVICES
            ["security", "find-generic-password", "-s", service],  # noqa: S607 - security is a controlled, known system binary
            capture_output=True,
            timeout=_VERSION_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "logged_out"
    return "logged_in" if proc.returncode == 0 else "logged_out"
