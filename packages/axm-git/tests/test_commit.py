from __future__ import annotations


def test_commit_tool() -> None:
    """Test commit tool initialization."""
    from axm_git.tools.commit import GitCommitTool

    tool = GitCommitTool()
    assert tool.name == "git_commit"
