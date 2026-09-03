"""Credential catalog — discovery and lookup of credential groups.

The catalog aggregates :class:`~axm_vault.models.CredentialGroup` bundles
contributed by packages through the ``axm.credentials`` entry-point group.
Vault itself contributes **no** groups: an empty catalog is the nominal
state when no package has registered any.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import cache
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import axm_config
from pydantic import BaseModel, ConfigDict, model_validator

from axm_vault.auth import AuthDependencySpec
from axm_vault.models import CredentialGroup, Sensitivity

if TYPE_CHECKING:
    from axm_vault.models import CredentialSpec

__all__ = [
    "Catalog",
    "CatalogRejection",
    "groups_from_provider",
    "load_catalog",
]

CREDENTIALS_GROUP = "axm.credentials"

_LOGGER = logging.getLogger(__name__)

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


@runtime_checkable
class _CredentialProvider(Protocol):
    """Runtime-narrowable callable contract for discovered providers."""

    def __call__(self) -> object:
        """Return the provider contribution."""
        ...


class CatalogRejection(BaseModel):  # type: ignore[explicit-any]
    """A credential entry point excluded from catalog discovery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_point: str
    reason: str


def groups_from_provider(
    entry_point: str,
    provider: object,
) -> tuple[tuple[CredentialGroup, ...], CatalogRejection | None]:
    """Validate one credential provider without leaking contribution failures."""
    if not isinstance(provider, _CredentialProvider):
        return (), CatalogRejection(
            entry_point=entry_point,
            reason=f"provider is not callable ({type(provider).__name__})",
        )

    try:
        provided = provider()
        if not isinstance(provided, Iterable):
            return (), CatalogRejection(
                entry_point=entry_point,
                reason=f"provider returned non-iterable {type(provided).__name__}",
            )
        groups: list[CredentialGroup] = []
        for item in provided:
            if not isinstance(item, CredentialGroup):
                return (), CatalogRejection(
                    entry_point=entry_point,
                    reason=(
                        "provider returned an item that is not a CredentialGroup: "
                        f"{type(item).__name__}"
                    ),
                )
            groups.append(item)
    except Exception as exc:  # noqa: BLE001 - isolate third-party providers
        return (), CatalogRejection(
            entry_point=entry_point,
            reason=f"provider raised {type(exc).__name__}: {exc}",
        )
    return tuple(groups), None


class Catalog(BaseModel):  # type: ignore[explicit-any]
    """An in-memory index of credential groups, keyed by group id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    groups_: tuple[CredentialGroup, ...] = ()
    rejections_: tuple[CatalogRejection, ...] = ()

    def __init__(
        self,
        groups: tuple[CredentialGroup, ...] = (),
        rejections: tuple[CatalogRejection, ...] = (),
        **data: object,
    ) -> None:
        super().__init__(
            groups_=tuple(groups),
            rejections_=tuple(rejections),
            **data,
        )

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

    def rejections(self) -> list[CatalogRejection]:
        """Return contributions rejected during catalog discovery."""
        return list(self.rejections_)

    def for_package(self, package: str) -> list[CredentialGroup]:
        """Return the groups contributed by ``package``."""
        return [g for g in self.groups_ if g.package == package]

    def all_specs(self) -> list[tuple[str, CredentialSpec]]:
        """Return every ``(group_id, spec)`` pair across all groups."""
        return [(g.id, spec) for g in self.groups_ for spec in g.specs]

    def auth_dependencies(self) -> list[AuthDependencySpec]:
        """Return every authentication dependency across all groups."""
        return [
            dependency
            for group in self.groups_
            for dependency in group.auth_dependencies
        ]


@cache
def load_catalog() -> Catalog:
    """Discover and index all ``axm.credentials`` groups.

    Reads the ``axm.credentials`` entry-points, calls each (a callable
    returning ``list[CredentialGroup]``) and indexes the groups by id.
    Returns an empty catalog when no entry-point is registered — the
    nominal state for vault itself. Cached so discovery runs once.
    """
    index: dict[str, CredentialGroup] = {}
    rejections: list[CatalogRejection] = []
    for endpoint in entry_points(group=CREDENTIALS_GROUP):
        rejection: CatalogRejection | None
        try:
            provider = endpoint.load()
        except Exception as exc:  # noqa: BLE001 - isolate third-party entry points
            rejection = CatalogRejection(
                entry_point=endpoint.name,
                reason=f"entry point load raised {type(exc).__name__}: {exc}",
            )
            groups: tuple[CredentialGroup, ...] = ()
        else:
            groups, rejection = groups_from_provider(endpoint.name, provider)

        if rejection is not None:
            rejections.append(rejection)
            _LOGGER.warning(
                "Rejected credential contribution %s: %s",
                rejection.entry_point,
                rejection.reason,
            )
            continue
        for group in groups:
            index[group.id] = group
    return Catalog(
        groups=tuple(index.values()),
        rejections=tuple(rejections),
    )
