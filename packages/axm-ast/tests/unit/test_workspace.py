"""Unit tests for axm_ast.core.workspace (pure-string parsing)."""

from __future__ import annotations

from axm_ast.core.workspace import parse_workspace_members


def test_members_multiline_array_parsed() -> None:
    """AC1: members in a multi-line array (comments / trailing comma) all returned."""
    text = (
        "[tool.uv.workspace]\n"
        "members = [\n"
        '    "packages/foo",  # first\n'
        '    "packages/bar",\n'
        '    "packages/baz",\n'
        "]\n"
    )
    assert parse_workspace_members(text) == [
        "packages/foo",
        "packages/bar",
        "packages/baz",
    ]


def test_members_single_line_array_parsed() -> None:
    """AC1: members on a single line are returned (no regression on the simple form)."""
    text = '[tool.uv.workspace]\nmembers = ["packages/foo", "packages/bar"]\n'
    assert parse_workspace_members(text) == ["packages/foo", "packages/bar"]


def test_members_absent_returns_empty() -> None:
    """AC3: a pyproject without [tool.uv.workspace] degrades to an empty list."""
    text = '[project]\nname = "x"\n'
    assert parse_workspace_members(text) == []


def test_malformed_pyproject_graceful() -> None:
    """AC3: broken TOML returns an empty list, no crash."""
    text = "[tool.uv.workspace\nmembers = [ this is not valid toml "
    assert parse_workspace_members(text) == []
