from __future__ import annotations

from axm_vault.models import CredentialGroup

__all__ = [
    "UnsupportedInstanceDeclarationError",
    "declare_instance",
    "list_instances",
]


class UnsupportedInstanceDeclarationError(RuntimeError):
    """Raised when a credential group cannot declare named instances."""


def list_instances(group: CredentialGroup) -> list[str]:
    """Return the instances declared by the group's source, in source order."""
    source = group.instances
    if source is None:
        return []
    return list(source.list_instances())


def declare_instance(group: CredentialGroup, instance: str) -> None:
    """Declare an instance through the group's source without provisioning it."""
    source = group.instances
    if source is None:
        raise UnsupportedInstanceDeclarationError(
            f"credential group {group.id!r} does not support instance declaration"
        )
    source.declare(instance)
