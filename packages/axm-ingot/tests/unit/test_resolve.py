from __future__ import annotations

from axm_ingot.uv import parse_workspace_members


def test_parse_workspace_members_raw() -> None:
    """AC1: returns the raw members declared under [tool.uv.workspace]."""
    text = '[tool.uv.workspace]\nmembers = ["packages/*", "other"]\n'
    assert parse_workspace_members(text) == ["packages/*", "other"]


def test_parse_members_empty_when_no_workspace() -> None:
    """AC1: returns [] when no [tool.uv.workspace] table is present."""
    text = '[project]\nname = "x"\n'
    assert parse_workspace_members(text) == []


def test_parse_members_malformed_text() -> None:
    """AC1: malformed TOML yields [] without raising."""
    text = "this is = not valid toml [[["
    assert parse_workspace_members(text) == []
