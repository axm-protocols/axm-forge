"""Canonical read authority for service-owned persisted targets."""

from __future__ import annotations

from pathlib import Path

from axm.tools.dependency_reads import current_read_contract, read_context_bound

__all__ = ["require_read_path"]


def require_read_path(path: str | Path) -> None:
    """Require read authority before opening a service's persisted target.

    Both explicit caller targets and implicit configured targets must pass here
    after canonical service resolution. Relative paths use the active contract's
    execution root, and symlinks use its canonical readable decision. Transport
    None explicitly denies reads and suppresses the ambient environment. Only
    legacy local callers with neither transport binding nor contract stay
    unrestricted; this helper never grants write authority.
    """
    contract = current_read_contract()
    if contract is None:
        if read_context_bound():
            raise PermissionError("read authority missing for persisted target")
        return
    resolved = contract.resolve(contract.execution_root, str(path))
    if not contract.readable(resolved):
        raise PermissionError(f"persisted target outside read authority: {resolved}")
