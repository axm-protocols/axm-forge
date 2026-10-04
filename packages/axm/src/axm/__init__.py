"""AXM CLI — Unified command-line interface for the AXM ecosystem."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from axm.tools import ToolMetadata, ToolNodeError, tool_metadata, tool_node
from axm.tools.base import AXMTool, ToolResult
from axm.tools.dependency_reads import (
    DependencyEnvironment,
    session_dependency_environment,
)
from axm.witnesses import ValidationFeedback, WitnessResult, WitnessRule

try:
    __version__ = version("axm")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "AXMTool",
    "DependencyEnvironment",
    "ToolMetadata",
    "ToolNodeError",
    "ToolResult",
    "ValidationFeedback",
    "WitnessResult",
    "WitnessRule",
    "__version__",
    "session_dependency_environment",
    "tool_metadata",
    "tool_node",
]
