"""Layered credential resolver.

Resolves a credential value by walking a fixed precedence of layers
(``env > file > keyring > default > prompt``). Each layer is consulted in
turn; the first to yield a value wins and is reported back in :class:`Resolved`
alongside the layer it came from and the originating spec.

The *file* layer reads the per-namespace TOML file under ``~/.axm`` **only**,
via :class:`axm_config.store.NamespaceStore` — vault never resolves the
``~/.axm`` path itself (that stays axm-config's responsibility), but it also
never consults the environment from this layer: provenance reported as
``file`` is always file-backed. The env tier lives solely in the ``env``
layer (``spec.env`` + aliases). The *keyring* layer is consulted **only** for
specs classified :data:`~axm_vault.models.Sensitivity.SECRET`.

Note: ``axm_config`` exposes no file-only accessor in its public
``__init__`` surface (``get``/``load`` mix env + file); vault therefore reads
through the internal-public :class:`~axm_config.store.NamespaceStore` to stay
file-only without re-implementing ``~/.axm`` resolution.
"""

from __future__ import annotations

import os
from getpass import getpass
from typing import TYPE_CHECKING

from axm_config.store import NamespaceStore
from pydantic import BaseModel, ConfigDict

from axm_vault.catalog import load_catalog
from axm_vault.models import CredentialSpec, Layer, Sensitivity
from axm_vault.secrets import as_secret
from axm_vault.store import KeyringStore, KeyringUnavailableError

if TYPE_CHECKING:
    from axm_vault.models import CredentialGroup

__all__ = [
    "MissingCredentialError",
    "Resolved",
    "Resolver",
    "bind",
    "get",
    "resolver",
]


class MissingCredentialError(Exception):
    """A required credential could not be resolved from any layer."""


class Resolved(BaseModel):  # type: ignore[explicit-any]
    """The outcome of resolving a single credential.

    Carries the resolved ``value``, the ``layer`` it was sourced from and the
    originating ``spec`` — but never masks: callers wrap secrets themselves
    (e.g. via :func:`~axm_vault.secrets.as_secret`).
    """

    model_config = ConfigDict(frozen=True)

    value: str
    layer: Layer
    spec: CredentialSpec


class Resolver:
    """Walk the layer precedence to resolve a credential value.

    The resolver is stateless and cheap to instantiate; a process-wide
    :data:`resolver` singleton is provided for the common case. Set
    ``interactive=True`` to enable the ``prompt`` layer (off by default so the
    resolver is safe in non-interactive contexts).
    """

    PRECEDENCE: tuple[Layer, ...] = ("env", "file", "keyring", "default", "prompt")

    def __init__(self, *, interactive: bool = False) -> None:
        self._interactive = interactive
        self._keyring = KeyringStore()

    def resolve(
        self, group: CredentialGroup, name: str, instance: str | None = None
    ) -> Resolved:
        """Resolve ``group.name`` by walking :data:`PRECEDENCE`.

        Returns the first layer that yields a value. Raises
        :class:`MissingCredentialError` when a *required* spec resolves to
        nothing across every layer.
        """
        spec = group.spec(name)
        for layer in self.PRECEDENCE:
            value = self._try(layer, spec, group, instance)
            if value is not None:
                return Resolved(value=value, layer=layer, spec=spec)
        if spec.required:
            raise MissingCredentialError(f"{group.id}.{name}")
        return Resolved(value=spec.default or "", layer="default", spec=spec)

    def probe(
        self,
        layer: Layer,
        spec: CredentialSpec,
        group: CredentialGroup,
        instance: str | None = None,
    ) -> bool:
        """Report whether ``layer`` supplies ``spec``, value-free.

        Reduces the layer's value to a boolean the instant it is read, so the
        value never escapes — the seam the *doctor* uses to build provenance
        without violating the never-leak invariant.
        """
        return self._try(layer, spec, group, instance) is not None

    def _try(
        self,
        layer: Layer,
        spec: CredentialSpec,
        group: CredentialGroup,
        instance: str | None,
    ) -> str | None:
        """Return the value ``layer`` provides for ``spec``, or ``None``."""
        match layer:
            case "env":
                return self._from_env(spec)
            case "file":
                return self._from_file(group, spec)
            case "keyring":
                return self._from_keyring(spec, group, instance)
            case "default":
                return spec.default
            case "prompt":
                return self._from_prompt(spec)
            case _:  # pragma: no cover - exhaustive over Layer
                return None

    @staticmethod
    def _from_env(spec: CredentialSpec) -> str | None:
        """Read ``spec.env`` then each alias (canonical wins over alias).

        An empty-string env var (``VAR=``) is treated as *absent*, not as an
        empty value: it must not win the env layer nor mask a value declared in
        a lower layer (file/keyring/default). A legitimately empty credential
        is vanishingly rare, so treating ``""`` as unset is the safer default.
        """
        for key in (spec.env, *spec.aliases):
            value = os.environ.get(key)
            if value:
                return value
        return None

    @staticmethod
    def _from_file(group: CredentialGroup, spec: CredentialSpec) -> str | None:
        """Read ``spec.name`` from the ``~/.axm/<group>.toml`` file *only*.

        Uses :class:`~axm_config.store.NamespaceStore` (file-only) rather than
        ``axm_config.get`` (which mixes an env tier under its own naming),
        so a value present only in the environment never surfaces here — the
        env tier belongs exclusively to the ``env`` layer.
        """
        value = NamespaceStore().read(group.id).get(spec.name)
        return value if isinstance(value, str) else None

    def _from_keyring(
        self, spec: CredentialSpec, group: CredentialGroup, instance: str | None
    ) -> str | None:
        """Consult the keyring only for SECRET specs.

        Degrades gracefully when the OS keyring is unavailable (headless host):
        the layer is skipped (returns ``None``) so resolution falls through to
        the lower layers (default) instead of crashing.
        """
        if spec.sensitivity is not Sensitivity.SECRET:
            return None
        try:
            return self._keyring.get(group.id, spec.name, instance)
        except KeyringUnavailableError:
            return None

    def keyring_available(self) -> bool:
        """Report whether the OS keyring backend is usable, value-free.

        Probes the backend with a read that resolves no real credential; a
        :class:`KeyringUnavailableError` means no usable backend (headless
        host). The *doctor* uses this to flag ``keyring unavailable`` without
        ever reading a secret value.
        """
        try:
            self._keyring.get("__axm_vault__", "__probe__")
        except KeyringUnavailableError:
            return False
        return True

    def _from_prompt(self, spec: CredentialSpec) -> str | None:
        """Prompt interactively when enabled and the spec declares one.

        A SECRET spec is read through :func:`getpass.getpass` so the typed
        value is never echoed to the terminal (never-leak invariant); a
        non-secret spec uses a visible :func:`input` prompt.
        """
        if not (self._interactive and spec.prompt):
            return None
        reader = getpass if spec.sensitivity is Sensitivity.SECRET else input
        return reader(spec.prompt) or None


resolver = Resolver()
"""Process-wide non-interactive resolver singleton."""


def _resolved_value(resolved: Resolved) -> str | None:
    """Return the value to bind, or ``None`` for an absent optional.

    The absence rule is sensitivity-agnostic: it applies identically to SECRET
    and CONFIG specs. An absent optional resolves to the synthetic ``default``
    layer with no real default declared; binding ``""`` (or ``SecretStr("")``)
    there would defeat a consumer's ``if x is None`` check. Such a case binds
    ``None`` instead. An explicit (even empty) default, or a value sourced from
    any real layer, is a genuine value and passes through unchanged.
    """
    spec = resolved.spec
    absent = resolved.layer == "default" and not spec.required and spec.default is None
    return None if absent else resolved.value


def get(group: str, name: str, instance: str | None = None) -> str:
    """Resolve ``group.name`` via the singleton :data:`resolver`.

    Convenience over ``resolver.resolve(load_catalog().group(group), name)``
    returning just the resolved value.
    """
    grp = load_catalog().group(group)
    return resolver.resolve(grp, name, instance).value


def bind[ModelT: BaseModel](
    model: type[ModelT], group: str, instance: str | None = None
) -> ModelT:
    """Build ``model`` from the resolved values of every spec in ``group``.

    Each field is keyed by ``spec.name``; SECRET specs are wrapped with
    :func:`~axm_vault.secrets.as_secret` so the consumer model holds
    ``SecretStr``. A missing *required* spec propagates
    :class:`MissingCredentialError`. The return type is the concrete ``model``
    type (generic over ``type[_ModelT]``), so a caller need not cast the
    result back to its model.
    """
    grp = load_catalog().group(group)
    data: dict[str, object] = {}
    for spec in grp.specs:
        resolved = resolver.resolve(grp, spec.name, instance)
        value = _resolved_value(resolved)
        if spec.sensitivity is Sensitivity.SECRET:
            data[spec.name] = as_secret(value)
        else:
            data[spec.name] = value
    return model.model_validate(data)
