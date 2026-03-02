"""AXM shared tool interfaces.

Re-exports:
    AXMTool: Abstract base class for deterministic tools.
    ToolResult: Immutable result of a tool execution.
"""

from __future__ import annotations

from axm.tools.base import AXMTool, ToolResult

__all__ = ["AXMTool", "ToolResult"]
