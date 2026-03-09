"""Result models for AXM operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScaffoldResult(BaseModel):
    """Result of a scaffolding operation."""

    model_config = {"extra": "forbid"}

    success: bool
    path: str
    message: str
    files_created: list[str] = Field(default_factory=list)


class ReserveResult(BaseModel):
    """Result of PyPI reservation operation."""

    model_config = {"extra": "forbid"}

    success: bool
    package_name: str
    version: str
    message: str
