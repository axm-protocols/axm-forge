"""Value-less credential catalog models.

These pydantic models describe credential *schemas* only — they never hold a
secret value (security invariant AC5). A :class:`CredentialSpec` declares where
and how a credential is fetched; a :class:`CredentialGroup` bundles the specs a
package requires.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "CredentialGroup",
    "CredentialSpec",
    "Layer",
    "Sensitivity",
]


class Sensitivity(StrEnum):
    """Classification of how sensitive a credential value is."""

    SECRET = "secret"  # noqa: S105 # enum label, not a password value
    CONFIG = "config"
    NONSENSITIVE = "nonsensitive"


type Layer = Literal["env", "file", "keyring", "default", "prompt"]
"""Resolution layer a credential may be sourced from."""


class CredentialSpec(BaseModel):  # type: ignore[explicit-any]
    """Schema for a single credential — value-less by construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    env: str
    kind: str
    sensitivity: Sensitivity = Sensitivity.SECRET
    required: bool = True
    default: str | None = None
    prompt: str | None = None
    aliases: tuple[str, ...] = ()


class CredentialGroup(BaseModel):  # type: ignore[explicit-any]
    """A bundle of credential specs declared by a package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    package: str
    title: str
    specs: tuple[CredentialSpec, ...]
    multi: bool = False

    def spec(self, name: str) -> CredentialSpec:
        """Return the spec named ``name``.

        Raises:
            KeyError: if no spec with that name exists in the group.
        """
        for candidate in self.specs:
            if candidate.name == name:
                return candidate
        raise KeyError(name)
