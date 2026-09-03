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
from collections.abc import Callable, Iterable
from queue import Empty, Queue
from threading import Thread
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel

if TYPE_CHECKING:
    from axm_vault import AuthDependencySpec

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
    "load_auth_declarations",
]

type ToolState = Literal["present", "absent"]
type AuthState = Literal[
    "logged_in",
    "logged_out",
    "not_installed",
    "undetermined",
]
type GitIdentityState = Literal["configured", "unconfigured"]
type GhConfigState = Literal["configured", "unconfigured", "not_installed"]

_VERSION_TIMEOUT_S = 5

# Per-tool auth wiring. ``cred`` is the credential file relative to ``~`` whose
# *existence* (never content) signals logged-in for credential-file tools.
# macOS-only auth wiring. On Darwin the token lives in the login Keychain, not
# in a credential file under ``~`` — the generic-password *service* name whose
# existence (exit code, never value) signals logged-in.


class ToolStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen result of probing a single external tool on ``PATH``."""

    name: str
    state: ToolState
    version: str | None = None
    path: str | None = None


class AuthStatus(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Frozen read-only auth state for a third-party binary."""

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


type CredentialProvider = Callable[[], Iterable[object]]
type AuthProbeResult = tuple[bool, object]


def load_auth_declarations() -> dict[str, AuthDependencySpec]:
    """Discover authentication declarations without making vault a bootstrap import."""
    try:
        from importlib.metadata import entry_points

        from axm_vault import AuthDependencySpec, CredentialGroup
    except ImportError:
        return {}

    declarations: dict[str, AuthDependencySpec] = {}
    for endpoint in entry_points(group="axm.credentials"):
        try:
            provider = cast("CredentialProvider", endpoint.load())
            groups = provider()
        except Exception:  # noqa: BLE001, S112 - isolate a broken distribution
            continue
        for group in groups:
            if not isinstance(group, CredentialGroup):
                continue
            for declaration in group.auth_dependencies:
                if isinstance(declaration, AuthDependencySpec):
                    declarations[declaration.name] = declaration
    return declarations


def _call_auth_declaration(
    declaration: AuthDependencySpec,
) -> AuthProbeResult:
    try:
        return True, declaration.status()
    except Exception:  # noqa: BLE001 - third-party probes must not escape doctor
        return False, None


def _collect_auth_probe(
    declaration: AuthDependencySpec,
    results: Queue[AuthProbeResult],
) -> None:
    results.put(_call_auth_declaration(declaration))


def _detect_declared_auth(declaration: AuthDependencySpec) -> AuthState:
    guard_delay = getattr(declaration, "guard_delay_s", None)
    if isinstance(guard_delay, int | float) and not isinstance(guard_delay, bool):
        results: Queue[AuthProbeResult] = Queue(maxsize=1)
        worker = Thread(
            target=_collect_auth_probe,
            args=(declaration, results),
            daemon=True,
        )
        worker.start()
        try:
            succeeded, observed = results.get(timeout=max(float(guard_delay), 0.0))
        except Empty:
            return "logged_out"
    else:
        succeeded, observed = _call_auth_declaration(declaration)

    if not succeeded:
        return "logged_out"
    if observed == "connected":
        return "logged_in"
    if observed == "tool_absent":
        return "not_installed"
    return "logged_out"


def detect_auth(tool: str) -> AuthStatus:
    """Report auth state through a package declaration when one is installed.

    A tool without a declaration degrades to presence detection: an installed
    binary has an undetermined auth state because its session cannot be verified.
    """
    declaration = load_auth_declarations().get(tool)
    if declaration is not None:
        return AuthStatus(
            tool=tool,
            state=_detect_declared_auth(declaration),
        )

    state: AuthState = (
        "undetermined" if shutil.which(tool) is not None else "not_installed"
    )
    return AuthStatus(tool=tool, state=state)


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
