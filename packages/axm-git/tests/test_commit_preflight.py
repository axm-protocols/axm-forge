from __future__ import annotations


def test_preflight_tool() -> None:
    """Test commit preflight tool initialization."""
    from axm_git.tools.commit_preflight import GitPreflightTool

    tool = GitPreflightTool()
    assert tool.name == "git_preflight"
