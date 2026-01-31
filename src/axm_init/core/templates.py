"""Template registry for project presets."""

from enum import Enum
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel


class TemplateType(str, Enum):
    """Available template types."""

    PYTHON = "python"
    MINIMAL = "minimal"


class TemplateInfo(BaseModel):
    """Template metadata."""

    name: str
    description: str
    path: Path

    model_config = {"extra": "forbid"}


# Bundled templates package
TEMPLATES_PKG = files("axm_init.templates")


def get_template_catalog() -> dict[TemplateType, TemplateInfo]:
    """Return available templates.

    Returns:
        Dictionary mapping TemplateType to TemplateInfo.
    """
    return {
        TemplateType.PYTHON: TemplateInfo(
            name="python",
            description="Modern Python package (hatch-vcs, ruff, pytest)",
            path=Path(str(TEMPLATES_PKG / "python-project")),
        ),
        TemplateType.MINIMAL: TemplateInfo(
            name="minimal",
            description="Minimal Python package (pyproject.toml only)",
            path=Path(str(TEMPLATES_PKG / "minimal")),
        ),
    }


def resolve_template(template: str) -> TemplateInfo:
    """Resolve template name to TemplateInfo.

    Args:
        template: Template name string (e.g., 'python', 'minimal').

    Returns:
        TemplateInfo for the requested template.

    Raises:
        ValueError: If template name is not found.
    """
    catalog = get_template_catalog()
    try:
        return catalog[TemplateType(template)]
    except (ValueError, KeyError) as e:
        available = ", ".join(t.value for t in TemplateType)
        msg = f"Unknown template '{template}'. Available: {available}"
        raise ValueError(msg) from e
