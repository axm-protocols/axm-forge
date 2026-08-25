"""axm-vault.

Catalog-resolver secrets manager (keyring + SecretStr) for AXM
"""

from __future__ import annotations

from axm_vault.catalog import Catalog, load_catalog
from axm_vault.doctor import Provenance, doctor_data
from axm_vault.models import (
    CredentialGroup,
    CredentialSpec,
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
    "KeyringStore",
    "Layer",
    "MissingCredentialError",
    "Provenance",
    "Resolved",
    "Resolver",
    "Sensitivity",
    "VaultDoctorTool",
    "VaultSetTool",
    "as_secret",
    "atomic_write",
    "bind",
    "doctor_data",
    "get",
    "load_catalog",
    "redact",
    "resolver",
    "rotate_secret",
    "run_setup",
]
