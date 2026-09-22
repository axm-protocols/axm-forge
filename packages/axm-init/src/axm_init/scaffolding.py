"""Public scaffold primitives and optional domain-provider discovery.

Entry points in ``axm.scaffold_providers`` are named after the scaffold kind
and load a zero-argument provider factory. Domain packages own their templates.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol, cast

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.framework import Framework
from axm_init.core.root_lock import target_root_lock
from axm_init.core.templates import TemplateLayer, TemplateType, template_chain
from axm_init.core.toml_edit import table_at
from axm_init.models.results import ScaffoldResult
from axm_init.rules import CheckResult, TomlTable, requires_toml, run_rules, section

__all__ = [
    "CheckResult",
    "CopierAdapter",
    "CopierConfig",
    "Framework",
    "ProviderError",
    "ScaffoldProvider",
    "ScaffoldRequest",
    "ScaffoldResult",
    "TemplateLayer",
    "TemplateType",
    "TomlTable",
    "load_provider",
    "render_scaffold",
    "requires_toml",
    "run_rules",
    "section",
    "table_at",
    "target_root_lock",
    "template_chain",
]


class ProviderError(ValueError):
    """An installed provider is ambiguous, invalid, or cannot be loaded."""


@dataclass(frozen=True)
class ScaffoldRequest:
    """Context used to select domain-owned layers (answers remain separate)."""

    kind: str
    framework: Framework | None = Framework.PYTHON
    member: bool = False


class ScaffoldProvider(Protocol):
    """Provider factory result; paths must remain available during rendering."""

    def layers(self, request: ScaffoldRequest) -> tuple[TemplateLayer, ...]:
        """Return ordered layers, including any required standard base layer."""
        ...


def load_provider(kind: str) -> ScaffoldProvider | None:
    """Load only the requested kind; absence is distinct from broken installs."""
    entries = list(entry_points(group="axm.scaffold_providers", name=kind))
    if not entries:
        return None
    if len(entries) != 1:
        raise ProviderError(f"Duplicate scaffold providers for {kind!r}")
    try:
        provider = entries[0].load()()
    except Exception as exc:
        raise ProviderError(f"Cannot load scaffold provider {kind!r}: {exc}") from exc
    if not callable(getattr(provider, "layers", None)):
        raise ProviderError(f"Scaffold provider {kind!r} must define layers(request)")
    return cast(ScaffoldProvider, provider)


def _validate_layers(layers: tuple[TemplateLayer, ...]) -> None:
    """Reject malformed ownership names before Copier writes answers files."""
    if not layers or not all(isinstance(layer, TemplateLayer) for layer in layers):
        raise ProviderError("Provider must return nonempty TemplateLayer values")
    names = [layer.name for layer in layers]
    if len(set(names)) != len(names):
        raise ProviderError("Duplicate template layer names")
    for layer in layers:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", layer.name):
            raise ProviderError(f"Invalid template layer name: {layer.name!r}")
        if not layer.path.is_dir():
            raise ProviderError(f"Template layer path does not exist: {layer.path}")


def render_scaffold(
    kind: str,
    destination: Path,
    data: Mapping[str, object],
    *,
    framework: Framework | None = Framework.PYTHON,
    member: bool = False,
) -> ScaffoldResult:
    """Create a scaffold in a missing/empty directory; never update user files.

    Installed providers take precedence. Built-in kinds retain their historical
    template-chain fallback. Templates are trusted as with init itself, and may
    execute Copier tasks. This is not transactional: task/render failures may
    leave partial output. Existing learning overlays use their dedicated route.
    """
    try:
        with target_root_lock(destination):
            if destination.is_symlink() or (
                destination.exists()
                and (not destination.is_dir() or any(destination.iterdir()))
            ):
                raise ProviderError(f"Scaffold destination is not empty: {destination}")
            provider = load_provider(kind)
            if provider is None:
                try:
                    template_type = TemplateType(kind)
                except ValueError as exc:
                    raise ProviderError(
                        f"No scaffold provider installed for {kind!r}"
                    ) from exc
                layers = template_chain(template_type, framework, member=member)
            else:
                layers = provider.layers(ScaffoldRequest(kind, framework, member))
            _validate_layers(layers)
            return CopierAdapter().apply_chain(list(layers), destination, data)
    except (ProviderError, KeyError, OSError) as exc:
        return ScaffoldResult(success=False, path=str(destination), message=str(exc))


def _provider_layers(request: ScaffoldRequest) -> tuple[TemplateLayer, ...] | None:
    provider = load_provider(request.kind)
    if provider is None:
        return None
    layers = provider.layers(request)
    _validate_layers(layers)
    return layers


def _legacy_experiment_layers() -> tuple[TemplateLayer, ...] | None:
    hook = getattr(load_provider("experiment"), "legacy_experiment_layers", None)
    if not callable(hook):
        return None
    layers = cast(tuple[TemplateLayer, ...], hook())
    _validate_layers(layers)
    return layers
