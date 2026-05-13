from __future__ import annotations

from axm_ast.core.workspace import _parse_workspace_members


def test_parse_workspace_members_glob() -> None:
    """_parse_workspace_members returns raw glob strings unchanged."""
    text = '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    result = _parse_workspace_members(text)
    assert result == ["packages/*"]
