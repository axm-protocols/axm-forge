"""AXM shared tool interfaces.

Re-exports:
    AXMTool: Abstract base class for deterministic tools.
    ToolResult: Immutable result of a tool execution.
    tool_node: Adapt an AXMTool into a DAG python-node function.
    ToolNodeError: Raised when a tool invoked as a node fails (fail-fast).
"""

from __future__ import annotations

from axm.tools.base import AXMTool, ToolResult
from axm.tools.node import ToolNodeError, tool_node

__all__ = ["AXMTool", "ToolNodeError", "ToolResult", "tool_node"]
