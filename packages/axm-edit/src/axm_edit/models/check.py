"""Structured diagnostics produced by the read-only ``batch_edit`` checks.

A :class:`CheckDiagnostic` is the single currency of the static-check layer:
it locates a finding (``op_index`` + ``file``), qualifies it (``severity`` +
stable ``code``) and explains it (``message`` + actionable ``hint``).  The
model carries no I/O and no rendering concern.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = ["CheckDiagnostic", "PreflightReport", "Severity"]

Severity = Literal["error", "warning"]
"""Closed set of diagnostic severities."""


class CheckDiagnostic(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """A single static-check finding on a batch operation.

    Attributes:
        op_index: 0-indexed position of the offending operation in the batch.
        file: Relative path targeted by that operation.
        severity: ``"error"`` blocks the batch, ``"warning"`` only informs.
        code: Stable machine-readable identifier (e.g. ``UNKNOWN_EDIT_KEY``).
        message: Human-readable explanation of what was found.
        hint: Actionable remediation advice.
    """

    op_index: int = Field(
        ...,
        ge=0,
        description="0-indexed position of the operation in the batch",
    )
    file: str = Field(..., min_length=1, description="Relative path to the file")
    severity: Severity = Field(
        default="error",
        description="Diagnostic severity (error blocks, warning informs)",
    )
    code: str = Field(..., min_length=1, description="Stable diagnostic code")
    message: str = Field(..., description="Human-readable explanation")
    hint: str = Field(default="", description="Actionable remediation hint")

    model_config = {"extra": "forbid"}


class PreflightReport(BaseModel):  # type: ignore[explicit-any]
    """A partitioned preflight verdict over a single batch.

    Attributes:
        diagnostics: Every diagnostic collected, in the order given.
        errors: The blocking subset, in input order.
        warnings: The non-blocking subset, in input order.
        blocking: True iff at least one diagnostic blocks the batch.
    """

    diagnostics: list[CheckDiagnostic] = Field(
        default_factory=list,
        description="Every diagnostic collected for the batch, in order",
    )
    errors: list[CheckDiagnostic] = Field(
        default_factory=list,
        description="Blocking diagnostics, in input order",
    )
    warnings: list[CheckDiagnostic] = Field(
        default_factory=list,
        description="Non-blocking diagnostics, in input order",
    )
    blocking: bool = Field(
        default=False,
        description="True iff at least one diagnostic blocks the batch",
    )

    model_config = {"extra": "forbid"}
