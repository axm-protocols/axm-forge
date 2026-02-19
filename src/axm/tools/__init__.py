"""AXM shared tool interfaces.

Re-exports:
    AXMTool: Abstract base class for deterministic tools.
    ToolResult: Immutable result of a tool execution.
    make_tool_class: Factory to wrap plain functions as AXMTool subclasses.
"""

from axm.tools.base import AXMTool, ToolResult, make_tool_class

__all__ = ["AXMTool", "ToolResult", "make_tool_class"]
