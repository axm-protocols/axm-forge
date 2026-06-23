"""Value-free credential provenance — the vault *doctor*.

:func:`doctor_data` answers a single question for every credential in the
catalog: *which layer would supply it, and is it present at all* — WITHOUT
ever reading or returning the value itself (security invariant AC2). It
probes each resolution layer for presence only, reducing the probe to a
boolean the instant a layer responds, so a plaintext secret never enters
the report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_vault.catalog import load_catalog
from axm_vault.models import Sensitivity
from axm_vault.resolver import Resolver

if TYPE_CHECKING:
    from axm_vault.catalog import Catalog
    from axm_vault.models import CredentialGroup, CredentialSpec, Layer

__all__ = ["Provenance", "doctor_data"]

type Provenance = dict[str, dict[str, str | bool]]
"""Per-credential report: ``{"group.name": {"layer": str, "present": bool}}``.

For a SECRET spec whose keyring backend is unavailable (headless host), the
entry additionally carries ``"keyring": "unavailable"`` so the doctor surfaces
the outage rather than silently reporting the credential as merely missing.
"""

_MISSING = "missing"
"""Sentinel layer used when no probed layer supplies the credential."""

_KEYRING_UNAVAILABLE = "unavailable"
"""Marker recorded under the ``keyring`` key when no usable backend exists."""

# Layers a non-interactive doctor probes, in precedence order. ``prompt`` is
# excluded on purpose: provenance must never block on stdin.
_PROBE_LAYERS: tuple[Layer, ...] = ("env", "file", "keyring", "default")


def doctor_data(
    package: str | None = None,
    *,
    catalog: Catalog | None = None,
    instance: str | None = None,
) -> Provenance:
    """Report the winning layer and presence of every credential, value-free.

    Args:
        package: When given, restrict the report to credential groups
            contributed by that package; otherwise cover the whole catalog.
        catalog: Catalog to inspect; defaults to the discovered
            :func:`~axm_vault.catalog.load_catalog` result.
        instance: Optional multi-instance segment forwarded to the probe.

    Returns:
        A :data:`Provenance` mapping ``"group.name"`` to ``{layer, present}``.
        ``layer`` is the first probed layer to supply the credential, or
        ``"missing"`` when none does; ``present`` mirrors that. The value
        itself is NEVER included (security invariant).
    """
    cat = catalog if catalog is not None else load_catalog()
    groups = cat.for_package(package) if package is not None else cat.groups()
    resolver = Resolver()
    keyring_ok = resolver.keyring_available()
    report: Provenance = {}
    for group in groups:
        for spec in group.specs:
            report[f"{group.id}.{spec.name}"] = _probe(
                resolver, group, spec, instance, keyring_ok=keyring_ok
            )
    return report


def _probe(
    resolver: Resolver,
    group: CredentialGroup,
    spec: CredentialSpec,
    instance: str | None,
    *,
    keyring_ok: bool = True,
) -> dict[str, str | bool]:
    """Find the winning layer for ``spec`` without retaining its value.

    Each layer is consulted for presence only; the value is dropped to a
    boolean immediately so it never escapes this function. When the keyring
    backend is unavailable and the spec is keyring-eligible (SECRET), the
    report is annotated ``keyring="unavailable"`` so the outage is visible.
    """
    entry: dict[str, str | bool] = {"layer": _MISSING, "present": False}
    if not keyring_ok and spec.sensitivity is Sensitivity.SECRET:
        entry["keyring"] = _KEYRING_UNAVAILABLE
    for layer in _PROBE_LAYERS:
        if resolver.probe(layer, spec, group, instance):
            entry["layer"] = layer
            entry["present"] = True
            return entry
    return entry
