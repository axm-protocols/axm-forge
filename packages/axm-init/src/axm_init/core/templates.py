"""Template path resolution for Copier scaffold templates."""

from __future__ import annotations

__all__ = [
    "TemplateInfo",
    "TemplateLayer",
    "TemplateType",
    "get_template_path",
    "template_chain",
]

from enum import StrEnum
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from axm_init.core.framework import Framework

# Bundled templates package
TEMPLATES_PKG = files("axm_init.templates")


class TemplateLayer(BaseModel):  # type: ignore[explicit-any]
    """One ordered Copier template application."""

    name: str
    path: Path
    data: dict[str, str]

    model_config = ConfigDict(extra="forbid", frozen=True)


class TemplateInfo(BaseModel):  # type: ignore[explicit-any]
    """Template metadata.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    name: str
    description: str
    path: Path

    model_config = ConfigDict(extra="forbid")


class TemplateType(StrEnum):
    """Available scaffold template types."""

    STANDALONE = "standalone"
    WORKSPACE = "workspace"
    MEMBER = "member"
    PAPER = "paper"
    EXPERIMENT = "experiment"
    LEARNING = "learning"


# Template directory per (template_type, framework). Python keeps its existing
# directories so nothing changes for the default path. New frameworks add their
# own bundled template dirs; missing combinations fall back to Python.
_TEMPLATE_DIRS: dict[tuple[TemplateType, Framework], str] = {
    (TemplateType.STANDALONE, Framework.PYTHON): "python-project",
    (TemplateType.WORKSPACE, Framework.PYTHON): "uv-workspace",
    (TemplateType.MEMBER, Framework.PYTHON): "workspace-member",
    (TemplateType.PAPER, Framework.PYTHON): "paper-submodule",
    (TemplateType.STANDALONE, Framework.NODE): "node-project",
    (TemplateType.STANDALONE, Framework.SVELTE): "svelte-project",
}


def get_template_path(
    template_type: TemplateType = TemplateType.STANDALONE,
    framework: Framework | None = Framework.PYTHON,
) -> Path:
    """Return path to a bundled Copier template for a template type + framework.

    Args:
        template_type: Type of template to look up.
        framework: Ecosystem the template targets (default ``python`` keeps the
            historical single-argument behaviour).

    Returns:
        Path to the bundled template directory.

    Raises:
        KeyError: If no template exists for the (type, framework) combination.
    """
    resolved_framework = framework or Framework.PYTHON
    dir_name = _TEMPLATE_DIRS[(template_type, resolved_framework)]
    return Path(str(TEMPLATES_PKG / dir_name))


def template_chain(
    template_type: TemplateType,
    framework: Framework | None,
    *,
    member: bool,
    existing: bool = False,
) -> tuple[TemplateLayer, ...]:
    """Resolve the ordered Copier layers for a scaffold request."""
    if template_type in (TemplateType.LEARNING, TemplateType.EXPERIMENT):
        from axm_init.scaffolding import ScaffoldRequest, _provider_layers

        return _provider_layers(
            ScaffoldRequest(template_type.value, framework, member, existing)
        )
    return (
        TemplateLayer(
            name=template_type.value,
            path=get_template_path(template_type, framework),
            data={},
        ),
    )
