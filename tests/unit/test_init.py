"""Unit tests for the ``axm`` package root re-export facade (AXM-1925)."""

from __future__ import annotations

import axm
from axm.hooks.base import HookAction, HookResult
from axm.tools.base import AXMTool, ToolResult
from axm.witnesses import ValidationFeedback, WitnessResult, WitnessRule

_CONTRACTS = (
    "ToolResult",
    "AXMTool",
    "HookResult",
    "HookAction",
    "WitnessResult",
    "ValidationFeedback",
    "WitnessRule",
    "__version__",
)


def test_root_reexports_core_contracts() -> None:
    """AC1: all 7 contracts + __version__ accessible as axm.<name>."""
    for name in _CONTRACTS:
        assert hasattr(axm, name), f"axm.{name} is not accessible"


def test_reexports_are_identity_not_copies() -> None:
    """AC2: re-exported symbols are identical (is) to the submodule definitions."""
    assert axm.ToolResult is ToolResult
    assert axm.AXMTool is AXMTool
    assert axm.HookResult is HookResult
    assert axm.HookAction is HookAction
    assert axm.WitnessResult is WitnessResult
    assert axm.ValidationFeedback is ValidationFeedback
    assert axm.WitnessRule is WitnessRule


def test_all_matches_namespace() -> None:
    """AC3: every name in axm.__all__ resolves via getattr; contracts present."""
    for name in axm.__all__:
        assert getattr(axm, name) is not None
    assert "ToolResult" in axm.__all__
    assert "__version__" in axm.__all__
