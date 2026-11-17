"""AXM shared tool interfaces.

Re-exports:
    contract_from_wire: Decode a legacy or versioned authority contract.
    contract_leaves: Return the ordered leaves of a contract conjunction.
    contract_to_wire: Encode a contract conjunction without flattening it.
    operator_authorized: Report the trusted interactive origin of a tool call.
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

from axm.tools.base import AXMTool, ToolImage, ToolMetadata, ToolResult, tool_metadata
from axm.tools.contract_wire import (
    contract_from_wire,
    contract_leaves,
    contract_to_wire,
)
from axm.tools.discovery import (
    TOOL_ENTRY_POINT_GROUPS,
    DuplicateToolError,
    tool_entry_points,
)
from axm.tools.node import ToolNodeError, load_tool, override_tools, tool_node
from axm.tools.operator_context import operator_authorized

__all__ = [
    "TOOL_ENTRY_POINT_GROUPS",
    "AXMTool",
    "DuplicateToolError",
    "ToolImage",
    "ToolMetadata",
    "ToolNodeError",
    "ToolResult",
    "contract_from_wire",
    "contract_leaves",
    "contract_to_wire",
    "load_tool",
    "operator_authorized",
    "override_tools",
    "tool_entry_points",
    "tool_metadata",
    "tool_node",
]
