from __future__ import annotations


def test_tag_tool() -> None:
    """Test tag tool initialization."""
    from axm_git.tools.tag import GitTagTool

    tool = GitTagTool()
    assert tool.name == "git_tag"
