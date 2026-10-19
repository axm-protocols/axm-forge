"""Filesystem authority of business services and their in-memory sessions.

Shared by every document service (Word, Excel, PowerPoint and future crafts)
so the decision lives once, here, and services only call it at their real I/O
points. A local caller with neither a transport binding nor a contract keeps
unrestricted legacy access; a bound caller (an explicit denial included) or any
contract is enforced.

An in-memory session created under enforced authority belongs to the exact
contract captured at creation, whether or not it tracks a file: its memory may
hold content read from other files, so readability of the tracked file alone
never transfers it. A session created by a legacy local caller is never adopted
by a bound caller. A file-backed session is additionally re-checked against its
current file. This is cooperative admission control, not an OS sandbox against
concurrent filesystem replacement (TOCTOU).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from axm.tools.dependency_reads import current_read_contract, read_context_bound
from axm.tools.read_authority import require_read_path
from axm.tools.write_authority import require_write_path

if TYPE_CHECKING:
    from pathlib import Path

    from axm.tools.write_scope import WriteContract

__all__ = [
    "SessionGrant",
    "authority_enforced",
    "capture_session_grant",
    "require_enforced_write_path",
    "require_legacy_authority",
    "require_session_access",
]


def authority_enforced() -> bool:
    """Whether filesystem authority applies to the current call.

    True when a transport bound authority (an explicit denial included) or a
    contract is active, false only for legacy local callers.
    """
    return read_context_bound() or current_read_contract() is not None


def require_enforced_write_path(path: str | Path) -> None:
    """Require write authority for a persisted output unless the call is legacy.

    Services call it before any side effect on the target's directory
    (temporary file, lock, ``mkdir``). Temporary files and locks a service
    derives from an authorised target are internal effects of that write, not
    targets the caller can choose, and need no grant of their own.

    Raises:
        PermissionError: If enforced authority does not grant the write.
    """
    if authority_enforced():
        require_write_path(path)


def require_legacy_authority(capability: str) -> None:
    """Refuse a capability that cannot be confined under enforced authority.

    For work the host cannot bound by file grants: an external renderer that
    follows references inside documents, or a persistent server or thread that
    would outlive the call's authority context.

    Raises:
        PermissionError: If filesystem authority is enforced.
    """
    if authority_enforced():
        raise PermissionError(f"{capability} is unavailable under enforced authority")


@dataclass(frozen=True)
class SessionGrant:
    """Authority an in-memory session was created under."""

    enforced: bool
    owner: WriteContract | None = None


def capture_session_grant() -> SessionGrant:
    """Capture the current authority for a session about to be created.

    Raises:
        PermissionError: If the call is bound to an explicit denial.
    """
    if not authority_enforced():
        return SessionGrant(enforced=False)
    owner = current_read_contract()
    if owner is None:
        raise PermissionError("read authority missing for a new session")
    return SessionGrant(enforced=True, owner=owner)


def require_session_access(grant: SessionGrant, source: Path | None) -> None:
    """Require the current authority to reach a session and its file.

    Legacy local callers are unrestricted. Otherwise the session must have
    been created under exactly the current contract, then its tracked file, if
    any, must still be readable.

    Args:
        grant: Authority captured when the session was created.
        source: File the session currently tracks, ``None`` when in memory.

    Raises:
        PermissionError: If the session was created by a legacy caller or under
            another contract, or its file is no longer readable.
    """
    if not authority_enforced():
        return
    if not grant.enforced or grant.owner is None:
        raise PermissionError("session was created outside this authority")
    if grant.owner != current_read_contract():
        raise PermissionError("session belongs to another authority")
    if source is not None:
        require_read_path(source)
