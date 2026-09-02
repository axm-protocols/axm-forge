"""axm-vault.

Catalog-resolver secrets manager (keyring + SecretStr) for AXM
"""

from __future__ import annotations

from axm_vault.catalog import Catalog, load_catalog
from axm_vault.doctor import Provenance, doctor_data
from axm_vault.instances import (
    UnsupportedInstanceDeclarationError,
    declare_instance,
    list_instances,
)
from axm_vault.models import (
    CredentialGroup,
    CredentialSpec,
    InstanceSource,
    Layer,
    Sensitivity,
)
from axm_vault.resolver import (
    MissingCredentialError,
    Resolved,
    Resolver,
    bind,
    get,
    resolver,
)
from axm_vault.secrets import MASK, as_secret, redact
from axm_vault.setup import run_setup
from axm_vault.store import SERVICE, KeyringStore, atomic_write, rotate_secret
from axm_vault.tools import VaultDoctorTool, VaultSetTool

__all__ = [
    "MASK",
    "SERVICE",
    "Catalog",
    "CredentialGroup",
    "CredentialSpec",
    "InstanceSource",
    "KeyringStore",
    "Layer",
    "MissingCredentialError",
    "Provenance",
    "Resolved",
    "Resolver",
    "Sensitivity",
    "UnsupportedInstanceDeclarationError",
    "VaultDoctorTool",
    "VaultSetTool",
    "as_secret",
    "atomic_write",
    "bind",
    "declare_instance",
    "doctor_data",
    "get",
    "list_instances",
    "load_catalog",
    "redact",
    "resolver",
    "rotate_secret",
    "run_setup",
]
