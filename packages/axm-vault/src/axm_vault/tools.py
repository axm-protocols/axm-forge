"""AXM tools for the vault — ``vault_doctor``, ``vault_set``, ``vault_delete``.

All three tools are deterministic :class:`~axm.tools.base.AXMTool`
implementations so they are reachable over MCP, the ``axm`` CLI and as DAG
nodes from a single ``axm.tools`` entry-point declaration. They uphold the
vault's central security invariant: **no tool ever serializes a SECRET
value**. ``vault_doctor`` returns value-free provenance; ``vault_set`` stores
a value but echoes only the storage target, never the value; ``vault_delete``
removes a stored credential and reports only the deletion target.
"""

from __future__ import annotations

import axm_config
from axm.tools.base import ToolResult

from axm_vault.catalog import load_catalog
from axm_vault.doctor import doctor_data
from axm_vault.models import Sensitivity
from axm_vault.store import KeyringStore

__all__ = ["VaultDeleteTool", "VaultDoctorTool", "VaultSetTool"]


class VaultDoctorTool:
    """Report credential provenance (layer + presence), never a value."""

    agent_hint = (
        "Report which layer (env/file/keyring/default/missing) supplies each "
        "credential and whether it is present — values are NEVER returned."
    )
    domain = "vault"
    tags = frozenset({"vault", "credentials", "doctor", "provenance"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "vault_doctor"

    def execute(
        self, *, package: str | None = None, instance: str | None = None
    ) -> ToolResult:
        """Return value-free provenance for the catalog (or one package)."""
        try:
            data = doctor_data(package, instance=instance)
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, data=dict(data))


class VaultSetTool:
    """Store a credential by ``group.name`` — keyring (SECRET) or config.

    NONSENSITIVE credentials are environment-only and are rejected outright:
    storing them would create a second, stale source of truth. The stored
    value is never echoed back — only the storage target is reported.
    """

    agent_hint = (
        "Store a credential: SECRET -> OS keyring, CONFIG -> axm-config; "
        "NONSENSITIVE is env-only and rejected. The value is never echoed."
    )
    domain = "vault"
    tags = frozenset({"vault", "credentials", "set"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "vault_set"

    def execute(
        self,
        *,
        group: str,
        name: str,
        value: str,
        instance: str | None = None,
    ) -> ToolResult:
        """Route ``group.name`` to its store by sensitivity; never echo value."""
        try:
            spec = load_catalog().group(group).spec(name)
            target = self._store(spec.sensitivity, group, name, value, instance)
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        return ToolResult(success=True, data={"stored": target})

    @staticmethod
    def _store(
        sensitivity: Sensitivity,
        group: str,
        name: str,
        value: str,
        instance: str | None,
    ) -> str:
        """Persist ``value`` to the backend for ``sensitivity``; return target.

        Raises:
            ValueError: when ``sensitivity`` is NONSENSITIVE (env-only).
        """
        target = f"{group}.{name}"
        match sensitivity:
            case Sensitivity.SECRET:
                KeyringStore().set(group, name, value, instance)
                return f"keyring:{target}"
            case Sensitivity.CONFIG:
                axm_config.set_(group, name, value)
                return f"config:{target}"
            case Sensitivity.NONSENSITIVE:
                msg = (
                    f"{target} is NONSENSITIVE (environment-only); "
                    "set it via its env var, it is never stored"
                )
                raise ValueError(msg)


class VaultDeleteTool:
    """Remove a stored credential by ``group.name`` from the keyring.

    The ``group.name`` is resolved through the catalog first (validating it is
    a known spec), then deleted from the OS keyring. Deletion is a **safe
    no-op** when the credential is already absent — the underlying store
    suppresses the keyring's ``Item not found`` error — so callers can delete
    idempotently. Only the deletion target is reported, never a value.
    """

    agent_hint = (
        "Delete a stored credential from the OS keyring by group.name; it is a "
        "safe no-op when the secret is already absent. No value is returned."
    )
    domain = "vault"
    tags = frozenset({"vault", "credentials", "delete"})

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "vault_delete"

    def execute(
        self, *, group: str = "", name: str = "", instance: str | None = None
    ) -> ToolResult:
        """Resolve ``group.name`` then delete it from the keyring (no-op if absent)."""
        try:
            spec = load_catalog().group(group).spec(name)
            KeyringStore().delete(group, spec.name, instance)
        except Exception as exc:  # noqa: BLE001 # MCP boundary: any error -> failure
            return ToolResult(success=False, error=str(exc))
        return ToolResult(
            success=True, data={"deleted": f"keyring:{group}.{spec.name}"}
        )
