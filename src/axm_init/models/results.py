"""Result models for AXM operations."""

from pydantic import BaseModel, Field


class ScaffoldResult(BaseModel):
    """Result of a scaffolding operation."""

    success: bool
    path: str
    message: str
    files_created: list[str] = Field(default_factory=list)
