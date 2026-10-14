"""Explicit write authority for persisted service targets."""

from __future__ import annotations

from pathlib import Path

from axm.tools.dependency_reads import current_read_contract

__all__ = ["require_write_path"]


def require_write_path(path: str | Path) -> None:
    """Require active write authority for a persisted target, or raise PermissionError.

    Use this before the canonical business mutation, with the host-configured
    path, not a path chosen by the model. Only allowed write prefixes count:
    readable roots/dependency aliases never grant writes. Resolution is relative
    to the contract execution root and follows symlinks through its canonical
    resolver. Missing authority is refused, including headless calls without an
    explicit contract. Local CLI callers may use their explicit AXM_WRITE_CONTRACT.
    """
    contract = current_read_contract()
    if contract is None:
        raise PermissionError("write authority missing for persisted target")
    resolved = contract.resolve(contract.execution_root, str(path))
    if not contract.permits(resolved):
        raise PermissionError(f"persisted target outside write authority: {resolved}")
