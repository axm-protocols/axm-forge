from __future__ import annotations

import pytest

from axm_ingot.uv import parse_workspace_members


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            '[tool.uv.workspace]\nmembers = ["packages/*", "other"]\n',
            ["packages/*", "other"],
            id="raw-members-returned",
        ),
        pytest.param(
            '[project]\nname = "x"\n',
            [],
            id="empty-when-no-workspace-table",
        ),
        pytest.param(
            "this is = not valid toml [[[",
            [],
            id="empty-on-malformed-toml",
        ),
        pytest.param(
            '[tool.uv.workspace]\nmembers = [1, 2, "packages/*"]\n',
            ["packages/*"],
            id="non-string-members-skipped",
        ),
    ],
)
def test_parse_workspace_members(text: str, expected: list[str]) -> None:
    """AC1: members under [tool.uv.workspace] are returned raw; a missing table
    or malformed TOML both yield [] without raising. Non-string members (e.g.
    integers) are skipped, matching resolve_workspace rather than str-coercing."""
    assert parse_workspace_members(text) == expected
