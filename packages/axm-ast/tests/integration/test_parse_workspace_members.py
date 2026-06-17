from __future__ import annotations

import pytest

from axm_ast.core.workspace import parse_workspace_members

pytestmark = pytest.mark.integration


def test_ast_parse_delegates_same_contract() -> None:
    """AC2: axm-ast parse_workspace_members preserves the raw-members contract.

    After delegating to axm-ingot, the public axm-ast entry point must still
    return the raw (non-expanded, non-globbed) member strings exactly as
    declared under [tool.uv.workspace], identical to the pre-refactor behavior.
    """
    text = '[tool.uv.workspace]\nmembers = ["packages/*", "other"]\n'
    assert parse_workspace_members(text) == ["packages/*", "other"]
