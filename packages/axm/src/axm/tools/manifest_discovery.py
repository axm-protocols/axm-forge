"""Installed resource providers for the common AXM tool resolver."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import json
import logging
import re
from dataclasses import dataclass
from typing import cast

from axm.tools.declarative import (
    DeclarativeTool,
    DeclarativeToolDefinition,
    DeclarativeToolManifest,
    load_declarative_manifest,
)

__all__ = ["DeclarativeToolReference", "declarative_tool_references"]
_GROUP = "axm.tool_manifests"
_PACKAGE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeclarativeToolReference:
    """Entry-point-compatible reference without a Python class per tool."""

    name: str
    value: str
    definition: DeclarativeToolDefinition
    group: str = _GROUP

    def load(self) -> DeclarativeTool:
        """Return an unbound adapter: discoverable headless, never ambient."""
        return DeclarativeTool(self.definition)


def _read_provider(ep: importlib.metadata.EntryPoint) -> DeclarativeToolManifest | None:
    if not _PACKAGE.fullmatch(ep.value):
        raise ValueError(f"manifest provider must name a resource package: {ep.value}")
    try:
        resource = importlib.resources.files(ep.value).joinpath("ui/tools.json")
        raw = json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        logger.warning("declarative provider %s unavailable: %s", ep.name, exc)
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"manifest for {ep.name} is not an object")
    manifest = load_declarative_manifest(cast(dict[str, object], raw))
    if manifest.addon_id != ep.name:
        raise ValueError(f"provider {ep.name} does not own addon {manifest.addon_id}")
    return manifest


def declarative_tool_references() -> dict[str, DeclarativeToolReference]:
    """Read ui/tools.json; missing resources warn, invalid contracts fail."""
    providers: set[str] = set()
    resolved: dict[str, DeclarativeToolReference] = {}
    for ep in importlib.metadata.entry_points(group=_GROUP):
        if ep.name in providers:
            raise ValueError(f"duplicate declarative provider: {ep.name}")
        providers.add(ep.name)
        manifest = _read_provider(ep)
        if manifest is None:
            continue
        for definition in manifest.tools:
            if definition.name in resolved:
                raise ValueError(f"duplicate declarative tool: {definition.name}")
            resolved[definition.name] = DeclarativeToolReference(
                definition.name,
                ep.value,
                definition,
            )
    return resolved
