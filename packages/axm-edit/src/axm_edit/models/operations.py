"""Pydantic models for batch file operations.

Defines the three operation types from the axm-edit spec:
- ``ReplaceOp`` — modify lines in an existing file
- ``CreateOp``  — create a new file
- ``DeleteOp``  — delete an existing file
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Edit(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """A single line-level edit within a replace operation.

    Attributes:
        line: Optional 1-indexed line hint in the **original** file.
              If provided, used as a starting point for searching ``old``.
              If omitted, ``old`` is searched in the entire file.
        old: Expected content to find and replace (validation anchor).
             May contain ``\\n`` for multi-line matches.
        new: Replacement content.
    """

    line: int | None = Field(
        default=None,
        ge=1,
        description="1-indexed line hint (optional — auto-search if omitted)",
    )
    old: str = Field(..., min_length=1, description="Expected content to find")
    new: str = Field(..., description="Replacement content")

    model_config = {"extra": "forbid"}


class ReplaceOp(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Modify lines in an existing file.

    All line numbers reference the file **as originally read**, before any
    edits are applied.  The engine sorts edits bottom-to-top to avoid
    line-shift problems.
    """

    op: Literal["replace"] = "replace"
    file: str = Field(..., min_length=1, description="Relative path to the file")
    edits: list[Edit] = Field(..., min_length=1, description="List of line edits")

    model_config = {"extra": "forbid"}


class CreateOp(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Create a new file.

    Fails if the file already exists unless ``overwrite`` is True.
    """

    op: Literal["create"] = "create"
    file: str = Field(..., min_length=1, description="Relative path to the file")
    content: str = Field(..., description="Full file content")
    overwrite: bool = Field(default=False, description="Allow overwriting")

    model_config = {"extra": "forbid"}


class DeleteOp(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Delete an existing file.

    Fails if the file does not exist.
    """

    op: Literal["delete"] = "delete"
    file: str = Field(..., min_length=1, description="Relative path to the file")

    model_config = {"extra": "forbid"}


Operation = Annotated[
    ReplaceOp | CreateOp | DeleteOp,
    Field(discriminator="op"),
]
"""Discriminated union of all operation types."""


class ValidationError(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """A single validation failure."""

    file: str
    line: int | None = None
    expected: str | None = None
    actual: str | None = None
    error: str | None = None

    model_config = {"extra": "forbid"}


class BatchResult(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Result of a batch edit operation.

    Atomicity contract (see :func:`axm_edit.core.engine.batch_apply`):
    atomicity is guaranteed at *validation* (all-or-nothing — a validation
    error rejects the whole batch before any write); the *apply* phase is
    best-effort with automatic rollback-to-checkpoint, so on any mid-apply
    exception ``success`` is ``False``, ``error`` is populated, ``checkpoint``
    holds the targeted snapshot, and every touched path has been restored to
    its pre-batch state.

    Attributes:
        success: Whether all operations were applied (``False`` if a
            validation error rejected the batch or a mid-apply exception
            triggered a rollback).
        checkpoint: Targeted-path snapshot captured before apply, usable for
            rollback; present whenever the apply phase was entered.
        applied: Total number of individual edits applied.
        summary: Counts of modified, created, and deleted files.
        error: Human-readable error message on failure.
        details: Detailed validation errors on failure.
    """

    success: bool
    checkpoint: str | None = None
    applied: int = 0
    summary: dict[str, int] = Field(
        default_factory=lambda: {"modified": 0, "created": 0, "deleted": 0},
    )
    error: str | None = None
    details: list[ValidationError] = Field(default_factory=list)
    lint_errors: list[str] = Field(default_factory=list)
    rollback_failed: bool = False

    model_config = {"extra": "forbid"}


class RollbackResult(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Outcome of a best-effort rollback.

    Rollback is a *strict inverse*: it only undoes what the batch did. It is
    also best-effort — every captured path is attempted even if an earlier one
    fails, so a partial rollback is fully observable instead of aborting
    mid-loop. ``ok`` is ``True`` only when the snapshot was well-formed and
    every captured path was restored.

    Attributes:
        restored: Relative paths successfully restored to their pre-batch state.
        unrestored: Relative paths that could not be restored (a filesystem
            error was raised while undoing them).
        valid: Whether the snapshot was well-formed and parseable.
    """

    restored: list[str] = Field(default_factory=list)
    unrestored: list[str] = Field(default_factory=list)
    valid: bool = True

    model_config = {"extra": "forbid"}

    @property
    def ok(self) -> bool:
        """True iff the snapshot was valid and nothing failed to restore."""
        return self.valid and not self.unrestored
