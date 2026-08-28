"""AXM shared tool interfaces.

Re-exports:
    AXMTool: Abstract base class for deterministic tools.
    ToolResult: Immutable result of a tool execution.
    ToolMetadata: Resolved facade/CLI discovery metadata for a tool.
    tool_metadata: Read a tool's optional discovery attributes.
    tool_node: Adapt an AXMTool into a DAG python-node function.
    ToolNodeError: Raised when a tool invoked as a node fails (fail-fast).
    override_tools: Substitute named tools for the extent of a block (test seam).
"""

from __future__ import annotations

from axm.tools.base import AXMTool, ToolMetadata, ToolResult, tool_metadata
from axm.tools.node import ToolNodeError, override_tools, tool_node

__all__ = [
    "AXMTool",
    "ToolMetadata",
    "ToolNodeError",
    "ToolResult",
    "override_tools",
    "tool_metadata",
    "tool_node",
]
