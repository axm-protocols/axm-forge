"""Project configuration models."""

from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    """Configuration for a Python project.

    This is the primary input model for project scaffolding.
    All fields are validated using Pydantic for Agent safety.
    """

    name: str = Field(..., min_length=1, description="Project name (PyPI compatible)")
    version: str = Field(default="0.1.0", description="Initial version")
    description: str = Field(default="", description="Project description")
    author: str = Field(default="", description="Author name")
    python_version: str = Field(default="3.12", description="Minimum Python version")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is valid for PyPI."""
        if not v or not v.strip():
            msg = "Project name cannot be empty"
            raise ValueError(msg)
        return v.strip().lower().replace(" ", "-")

    model_config = {"extra": "forbid"}


class ProjectMetadata(BaseModel):
    """Metadata extracted from an existing project.

    Used by the Auditor to capture the current state.
    """

    name: str
    version: str
    path: str
    has_pyproject: bool = False
    has_readme: bool = False
    has_license: bool = False
    has_tests: bool = False

    model_config = {"extra": "forbid"}
