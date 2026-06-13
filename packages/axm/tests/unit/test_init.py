from __future__ import annotations

import axm
from axm import tools


def test_root_reexports_tool_node_surface() -> None:
    """AC1, AC3: the four names import from ``axm``, same objects as ``axm.tools``."""
    assert axm.tool_node is tools.tool_node
    assert axm.ToolNodeError is tools.ToolNodeError
    assert axm.ToolMetadata is tools.ToolMetadata
    assert axm.tool_metadata is tools.tool_metadata


def test_all_contains_tool_node_surface() -> None:
    """AC2: all four names appear in ``axm.__all__``."""
    expected = {"tool_node", "ToolNodeError", "ToolMetadata", "tool_metadata"}
    assert expected <= set(axm.__all__)
