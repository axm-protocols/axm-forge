"""Unit tests for GitCloneTool (pure, no I/O)."""

from __future__ import annotations

from axm_git.tools.clone import GitCloneTool


class TestGitCloneToolName:
    """Unit tests for the GitCloneTool name property (no I/O)."""

    def test_tool_name(self) -> None:
        """The tool name property returns the registered MCP name."""
        assert GitCloneTool().name == "git_clone"
