"""Orchestrate missing-secret detection on top of axm-vault.

This module ORCHESTRATES; it never POSSESSES a secret. :func:`missing_secrets`
reads the vault catalog (:func:`axm_vault.load_catalog`) and the value-free
resolver provenance (:func:`axm_vault.doctor.doctor_data`) to surface the specs
that resolve to ``"missing"`` — without ever reading a secret value.
:func:`provision_missing` delegates to vault's :func:`axm_vault.setup.run_setup`
*only* on confirmation; doctor never writes a secret itself (every write goes
through vault's API — the SRP invariant).

Unlike :mod:`axm_doctor.detect` (bootstrap-sensitive, no AXM import), this is
the orchestration seam, so it depends on axm-vault directly.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping

from axm_vault import load_catalog
from axm_vault.doctor import doctor_data
from axm_vault.setup import run_setup
from axm_vault.store import KeyringStore
from pydantic import BaseModel

__all__ = [
    "MissingSecret",
    "ProvisionResult",
    "missing_secrets",
    "provision_missing",
]

_MISSING = "missing"


class MissingSecret(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """A credential spec that resolves to ``"missing"`` across every layer.

    Value-less by construction: it carries only the coordinates of the spec
    and a copy-pasteable recovery hint (``setup_hint``). ``required``
    preserves the catalog distinction between indispensable and optional
    credentials (the catalog default is ``True``). ``instance`` identifies
    the account concerned, while ``awaiting_instance`` marks a multi-instance
    group that declares no account yet. The secret value itself NEVER transits
    axm_doctor.
    """

    group: str
    name: str
    package: str
    setup_hint: str
    required: bool
    instance: str | None = None
    awaiting_instance: bool = False


class ProvisionResult(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """Outcome of :func:`provision_missing`.

    On a dry-run (``confirm=False``) ``provisioned`` is False and ``groups``
    lists the groups it WOULD prompt for. On a confirmed run ``provisioned``
    is True ONLY when a post-setup re-scan confirms every previously-missing
    spec now resolves — delegating to vault's setup driver is not proof the
    user actually supplied the secrets (they may skip/empty the prompts).
    ``still_missing`` lists the specs that remain unresolved after the run
    (always empty on a dry-run), so a partial provisioning is reported truthfully
    rather than as a false green.
    """

    provisioned: bool
    groups: list[str]
    still_missing: list[str] = []
    reason: str | None = None


#: Segment count of an instance-qualified coordinate: group, instance, name.
_INSTANCE_SEGMENTS = 3


def _is_served(
    provenance: Mapping[str, Mapping[str, str | bool]],
    group_id: str,
    name: str,
    instance: str | None = None,
) -> bool:
    """Report whether the provenance holds a concrete layer for a credential.

    The report is keyed by the canonical coordinate composed by
    :meth:`~axm_vault.store.KeyringStore.username`, which percent-escapes every
    segment: a group id carrying a literal dot is therefore NOT addressable by
    plain concatenation. Composing the key here through the very same function
    the producer uses is what keeps the two sides from drifting apart.

    Multi-instance groups are reported one entry per account. Looking up
    only the exact coordinate prevents a served sibling account from hiding
    an account whose credential is still missing.

    Args:
        provenance: The value-free report returned by ``doctor_data``.
        group_id: The credential group id, unescaped.
        name: The credential name within that group.
        instance: The account identity within a multi-instance group.

    Returns:
        ``True`` when the exact credential/account entry carries a
        concrete (non-missing) layer, ``False`` otherwise.
    """
    coordinate = KeyringStore.username(group_id, name, instance)
    entry = provenance.get(coordinate)
    return entry is not None and entry.get("layer") != _MISSING


def missing_secrets() -> list[MissingSecret]:
    """Return the catalog specs that resolve to ``"missing"``, value-free.

    Reads the vault catalog and the value-free provenance report; a spec is
    reported when no resolver layer supplies it. An empty catalog (the
    nominal state for vault today) yields ``[]`` gracefully.
    """
    catalog = load_catalog()
    provenance = doctor_data(catalog=catalog)
    missing: list[MissingSecret] = []
    for group in catalog.groups():
        if group.multi and group.instances is not None:
            declared_instances = tuple(group.instances.list_instances())
            awaiting_instance = not declared_instances
            instances: tuple[str | None, ...] = declared_instances or (None,)
        else:
            awaiting_instance = False
            instances = (None,)

        for spec in group.specs:
            for instance in instances:
                if _is_served(provenance, group.id, spec.name, instance):
                    continue
                missing.append(
                    MissingSecret(
                        group=group.id,
                        name=spec.name,
                        package=group.package,
                        setup_hint=f"axm-vault set {group.id} {spec.name}",
                        required=spec.required,
                        instance=instance,
                        awaiting_instance=awaiting_instance,
                    )
                )
    return missing


def provision_missing(*, confirm: bool = False) -> ProvisionResult:
    """Plan (and on ``confirm`` execute) provisioning of missing secrets.

    Collects the distinct groups owning at least one missing spec. With
    ``confirm=False`` it returns the plan without prompting or storing. With
    ``confirm=True`` it delegates to vault's :func:`run_setup` (one call per
    group, restricted via ``only=``); doctor never stores a secret itself.
    """
    groups: list[str] = []
    for secret in missing_secrets():
        if secret.group not in groups:
            groups.append(secret.group)
    if confirm and not sys.stdin.isatty():
        return ProvisionResult(
            provisioned=False,
            groups=groups,
            reason="non-interactive shell: cannot prompt for secrets",
        )
    if not confirm:
        return ProvisionResult(provisioned=False, groups=groups)
    for group in groups:
        try:
            run_setup(only=group)
        except SystemExit as exc:  # vault's setup driver aborts via SystemExit
            return ProvisionResult(
                provisioned=False,
                groups=groups,
                reason=f"vault setup aborted for {group} (exit {exc.code})",
            )
    # Re-scan: delegating to run_setup is NOT proof a secret was supplied (the
    # user may skip/empty a prompt). Truth comes from re-resolving the catalog.
    still_missing = [f"{s.group}.{s.name}" for s in missing_secrets()]
    provisioned = bool(groups) and not still_missing
    reason = None if provisioned else "some secrets remain unresolved after setup"
    return ProvisionResult(
        provisioned=provisioned,
        groups=groups,
        still_missing=still_missing,
        reason=reason if still_missing else None,
    )
