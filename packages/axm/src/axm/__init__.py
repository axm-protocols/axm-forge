"""AXM CLI — Unified command-line interface for the AXM ecosystem."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from axm.tools import ToolMetadata, ToolNodeError, tool_metadata, tool_node
from axm.tools.access import ToolAccessDenied, tool_access_scope, tool_execution_guard
from axm.tools.base import AXMTool, ToolResult
from axm.tools.declarative import (
    DeclarativeTool,
    DeclarativeToolDefinition,
    DeclarativeToolManifest,
    load_declarative_manifest,
    tool_scope_sha256,
    validate_declarative_schema,
)
from axm.tools.dependency_reads import (
    DependencyEnvironment,
    session_dependency_environment,
)
from axm.tools.read_authority import require_read_path
from axm.tools.write_authority import require_write_path
from axm.witnesses import ValidationFeedback, WitnessResult, WitnessRule

try:
    __version__ = version("axm")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "AXMTool",
    "DeclarativeTool",
    "DeclarativeToolDefinition",
    "DeclarativeToolManifest",
    "DependencyEnvironment",
    "ToolAccessDenied",
    "ToolMetadata",
    "ToolNodeError",
    "ToolResult",
    "ValidationFeedback",
    "WitnessResult",
    "WitnessRule",
    "__version__",
    "load_declarative_manifest",
    "require_read_path",
    "require_write_path",
    "session_dependency_environment",
    "tool_access_scope",
    "tool_execution_guard",
    "tool_metadata",
    "tool_node",
    "tool_scope_sha256",
    "validate_declarative_schema",
]
