"""Result models for AXM operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScaffoldResult(BaseModel):  # type: ignore[explicit-any]
    """Result of a scaffolding operation.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    path: str
    message: str
    files_created: list[str] = Field(default_factory=list)


class ReserveResult(BaseModel):  # type: ignore[explicit-any]
    """Result of PyPI reservation operation.

    Note: ``type: ignore[explicit-any]`` flags pydantic ``BaseModel``
    internals (third-party).
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    package_name: str
    version: str
    message: str
