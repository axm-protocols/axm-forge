"""Credential catalog — discovery and lookup of credential groups.

The catalog aggregates :class:`~axm_vault.models.CredentialGroup` bundles
contributed by packages through the ``axm.credentials`` entry-point group.
Vault itself contributes **no** groups: an empty catalog is the nominal
state when no package has registered any.
"""

from __future__ import annotations

import re
from functools import cache
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

from axm_vault.models import CredentialGroup, Sensitivity

if TYPE_CHECKING:
    from axm_vault.models import CredentialSpec

__all__ = ["Catalog", "load_catalog"]

CREDENTIALS_GROUP = "axm.credentials"

# A spec name that reaches axm_config (the SECRET presence sentinel keyed by
# ``<name>_set``, or a CONFIG value keyed by ``<name>``) must be a valid
# axm-config key. axm-config's key charset is ``^[A-Za-z0-9_]+$`` (private
# there); it is mirrored here so the catalog can reject un-round-trippable
# names at load time rather than failing later inside run_setup. NONSENSITIVE
# specs are env-only and never written to axm_config, so they are exempt.
_CONFIG_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
_STORABLE: frozenset[Sensitivity] = frozenset({Sensitivity.SECRET, Sensitivity.CONFIG})


class Catalog(BaseModel):  # type: ignore[explicit-any]
    """An in-memory index of credential groups, keyed by group id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    groups_: tuple[CredentialGroup, ...] = ()

    def __init__(
        self, groups: tuple[CredentialGroup, ...] = (), **data: object
    ) -> None:
        super().__init__(groups_=tuple(groups), **data)

    @model_validator(mode="after")
    def _validate_spec_names(self) -> Catalog:
        """Reject SECRET/CONFIG spec names that no axm-config key can hold.

        A SECRET spec writes a presence sentinel keyed by ``<name>_set`` and a
        CONFIG spec writes its value keyed by ``<name>``; both go through
        ``axm_config.set_``, whose key charset is ``^[A-Za-z0-9_]+$``. A name
        carrying ``.``/``-`` could never round-trip, so it is a structural
        error caught here (the same path :func:`load_catalog` takes) instead
        of surfacing as a ``ConfigError`` mid-``run_setup``. NONSENSITIVE
        specs are env-only and exempt.
        """
        for group in self.groups_:
            for spec in group.specs:
                if spec.sensitivity in _STORABLE and not _CONFIG_KEY_RE.match(
                    spec.name
                ):
                    msg = (
                        f"invalid credential spec name {spec.name!r} in group "
                        f"{group.id!r}: a {spec.sensitivity.value.upper()} name "
                        f"must match {_CONFIG_KEY_RE.pattern} to be a valid "
                        "axm-config key"
                    )
                    raise ValueError(msg)
        return self

    def group(self, gid: str) -> CredentialGroup:
        """Return the group identified by ``gid``.

        Raises:
            KeyError: if no group with that id is registered.
        """
        for candidate in self.groups_:
            if candidate.id == gid:
                return candidate
        raise KeyError(f"no credential group with id {gid!r}")

    def groups(self) -> list[CredentialGroup]:
        """Return every registered group."""
        return list(self.groups_)

    def for_package(self, package: str) -> list[CredentialGroup]:
        """Return the groups contributed by ``package``."""
        return [g for g in self.groups_ if g.package == package]

    def all_specs(self) -> list[tuple[str, CredentialSpec]]:
        """Return every ``(group_id, spec)`` pair across all groups."""
        return [(g.id, spec) for g in self.groups_ for spec in g.specs]


@cache
def load_catalog() -> Catalog:
    """Discover and index all ``axm.credentials`` groups.

    Reads the ``axm.credentials`` entry-points, calls each (a callable
    returning ``list[CredentialGroup]``) and indexes the groups by id.
    Returns an empty catalog when no entry-point is registered — the
    nominal state for vault itself. Cached so discovery runs once.
    """
    index: dict[str, CredentialGroup] = {}
    for endpoint in entry_points(group=CREDENTIALS_GROUP):
        provider = endpoint.load()
        for group in provider():
            index[group.id] = group
    return Catalog(groups=tuple(index.values()))
