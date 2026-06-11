"""AXM CLI — Unified command-line interface for the AXM ecosystem."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from axm.hooks.base import HookAction, HookResult
from axm.tools.base import AXMTool, ToolResult
from axm.witnesses import ValidationFeedback, WitnessResult, WitnessRule

try:
    __version__ = version("axm")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "AXMTool",
    "HookAction",
    "HookResult",
    "ToolResult",
    "ValidationFeedback",
    "WitnessResult",
    "WitnessRule",
    "__version__",
]
