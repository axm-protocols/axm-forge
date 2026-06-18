"""Unit tests for :class:`axm_anvil.tools.rename.RenameTool` (no real I/O).

The tool surface is exercised through its public boundary ``RenameTool``;
the internal ``RenameSymbols`` / ``_discover_callers`` are never touched
directly. Filesystem fixtures use ``tmp_path`` to give the tool a real
workspace root, but assertions target the in-memory ``ToolResult`` shape
and failure semantics.
"""

from __future__ import annotations

from axm_anvil.tools.rename import RenameTool


def test_name_is_anvil_rename() -> None:
    """AC2: the tool advertises ``anvil_rename`` for registry lookup."""
    assert RenameTool().name == "anvil_rename"
