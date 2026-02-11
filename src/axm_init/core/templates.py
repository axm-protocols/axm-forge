"""Template path for python-project scaffold."""

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


def get_template_path() -> Path:
    """Return path to the python-project Copier template.

    Returns:
        Path to the bundled python-project template directory.
    """
    return Path(str(TEMPLATES_PKG / "python-project"))
