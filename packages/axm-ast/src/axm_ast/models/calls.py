"""Pydantic models for call-site analysis.

These models represent function/method call locations found via
tree-sitter parsing, used by the caller analysis feature.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CallSite(BaseModel):
    """A single function/method call location.

    Example:
        >>> cs = CallSite(
        ...     module="cli",
        ...     symbol="greet",
        ...     line=42,
        ...     column=8,
        ...     context="main",
        ...     call_expression='greet("world")',
        ... )
        >>> cs.module
        'cli'
    """

    module: str = Field(description="Dotted module name")
    symbol: str = Field(description="Called symbol name")
    line: int = Field(description="Line number (1-indexed)")
    column: int = Field(description="Column offset (0-indexed)")
    context: str | None = Field(
        default=None,
        description="Enclosing function/class name",
    )
    call_expression: str = Field(
        description="Raw text of the call expression",
    )
