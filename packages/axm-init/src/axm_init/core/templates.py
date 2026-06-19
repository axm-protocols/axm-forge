"""Template path resolution for Copier scaffold templates."""

from __future__ import annotations

__all__ = ["TemplateInfo", "TemplateType", "get_template_path"]

from enum import StrEnum
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from axm_init.core.framework import Framework

# Bundled templates package
TEMPLATES_PKG = files("axm_init.templates")


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


# Template directory per (template_type, framework). Python keeps its existing
# directories so nothing changes for the default path. New frameworks add their
# own bundled template dirs; missing combinations fall back to Python.
_TEMPLATE_DIRS: dict[tuple[TemplateType, Framework], str] = {
    (TemplateType.STANDALONE, Framework.PYTHON): "python-project",
    (TemplateType.WORKSPACE, Framework.PYTHON): "uv-workspace",
    (TemplateType.MEMBER, Framework.PYTHON): "workspace-member",
    (TemplateType.STANDALONE, Framework.NODE): "node-project",
    # Svelte standalone reuses the node template for the POC; a dedicated
    # "svelte-project" template would slot in here.
    (TemplateType.STANDALONE, Framework.SVELTE): "node-project",
}


def get_template_path(
    template_type: TemplateType = TemplateType.STANDALONE,
    framework: Framework = Framework.PYTHON,
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
    dir_name = _TEMPLATE_DIRS[(template_type, framework)]
    return Path(str(TEMPLATES_PKG / dir_name))
