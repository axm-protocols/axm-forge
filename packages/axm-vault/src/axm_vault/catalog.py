"""Credential catalog — discovery and lookup of credential groups.

The catalog aggregates :class:`~axm_vault.models.CredentialGroup` bundles
contributed by packages through the ``axm.credentials`` entry-point group.
Vault itself contributes **no** groups: an empty catalog is the nominal
state when no package has registered any.
"""

from __future__ import annotations

from functools import cache
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

import axm_config
from pydantic import BaseModel, ConfigDict, model_validator

from axm_vault.models import CredentialGroup, Sensitivity

if TYPE_CHECKING:
    from axm_vault.models import CredentialSpec

__all__ = ["Catalog", "load_catalog"]

CREDENTIALS_GROUP = "axm.credentials"

# A group id is used verbatim as an axm-config *namespace* (the CONFIG value is
# keyed ``set_(group.id, name, ...)``), and a SECRET/CONFIG spec name is used as
# an axm-config *key*. Both charsets are owned by axm-config; rather than mirror
# them here (the manual mirror has already diverged once), validation delegates
# to ``axm_config.validate_segment`` — the single canonical rule — so the
# catalog can reject un-round-trippable identifiers at load time rather than
# failing later inside ``run_setup``. NONSENSITIVE specs are env-only and never
# reach axm_config, so their names are exempt (their group id is still checked,
# since it namespaces the whole group).
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
    def _validate_names(self) -> Catalog:
        """Reject group ids / spec names that no axm-config segment can hold.

        Every ``group.id`` namespaces the group's axm-config writes
        (``set_(group.id, ...)``) and every SECRET/CONFIG spec name is used as
        an axm-config key; both must round-trip through ``axm_config.set_``.
        The charsets are axm-config's (namespace ``^[a-z0-9]+(\\.[a-z0-9]+)*$``,
        key ``^[a-z0-9]+(_[a-z0-9]+)*$``) so validation delegates to the
        canonical :func:`axm_config.validate_segment` rather than mirroring the
        patterns (the mirror had already diverged). An id/name that could never
        round-trip is a structural error caught here (the same path
        :func:`load_catalog` takes) instead of surfacing as a ``ConfigError``
        mid-``run_setup``. NONSENSITIVE spec names are env-only and exempt; the
        group id is checked regardless. axm-config's ``ConfigError`` is
        normalised to ``ValueError`` so the failure arrives as pydantic's
        ``ValidationError`` like any other model-validation error.
        """
        try:
            for group in self.groups_:
                axm_config.validate_segment(group.id, kind="namespace")
                for spec in group.specs:
                    if spec.sensitivity in _STORABLE:
                        axm_config.validate_segment(spec.name, kind="key")
        except axm_config.ConfigError as exc:
            raise ValueError(str(exc)) from exc
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
