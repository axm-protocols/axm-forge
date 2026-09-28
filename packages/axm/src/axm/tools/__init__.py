"""AXM shared tool interfaces.

Re-exports:
    AXMTool: Abstract base class for deterministic tools.
    ToolResult: Immutable result of a tool execution.
    ToolMetadata: Resolved facade/CLI discovery metadata for a tool.
    tool_metadata: Read a tool's optional discovery attributes.
    tool_node: Adapt an AXMTool into a DAG python-node function.
    load_tool: Resolve an AXM tool by name (override-aware).
    tool_entry_points: The single resolver of tool names to entry points.
    TOOL_ENTRY_POINT_GROUPS: Tool entry-point groups, highest precedence first.
    DuplicateToolError: One entry-point group publishes a tool name twice.
    ToolNodeError: Raised when a tool invoked as a node fails (fail-fast).
    override_tools: Substitute named tools for the extent of a block (test seam).
"""

from __future__ import annotations

from axm.tools.base import AXMTool, ToolMetadata, ToolResult, tool_metadata
from axm.tools.discovery import (
    TOOL_ENTRY_POINT_GROUPS,
    DuplicateToolError,
    tool_entry_points,
)
from axm.tools.node import ToolNodeError, load_tool, override_tools, tool_node

__all__ = [
    "TOOL_ENTRY_POINT_GROUPS",
    "AXMTool",
    "DuplicateToolError",
    "ToolMetadata",
    "ToolNodeError",
    "ToolResult",
    "load_tool",
    "override_tools",
    "tool_entry_points",
    "tool_metadata",
    "tool_node",
]
