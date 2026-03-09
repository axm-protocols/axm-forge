"""Template path resolution for Copier scaffold templates."""

from __future__ import annotations

__all__ = ["TemplateInfo", "TemplateType", "get_template_path"]

from enum import StrEnum
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel

# Bundled templates package
TEMPLATES_PKG = files("axm_init.templates")


class TemplateInfo(BaseModel):
    """Template metadata."""

    name: str
    description: str
    path: Path

    model_config = {"extra": "forbid"}


class TemplateType(StrEnum):
    """Available scaffold template types."""

    STANDALONE = "standalone"
    WORKSPACE = "workspace"
    MEMBER = "member"


_TEMPLATE_DIRS: dict[TemplateType, str] = {
    TemplateType.STANDALONE: "python-project",
    TemplateType.WORKSPACE: "uv-workspace",
    TemplateType.MEMBER: "workspace-member",
}


def get_template_path(
    template_type: TemplateType = TemplateType.STANDALONE,
) -> Path:
    """Return path to a bundled Copier template.

    Args:
        template_type: Type of template to look up.

    Returns:
        Path to the bundled template directory.
    """
    dir_name = _TEMPLATE_DIRS[template_type]
    return Path(str(TEMPLATES_PKG / dir_name))
