"""Integration: shared scaffolding seam against a real workspace on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.scaffolder import (
    build_member_data,
    read_workspace_name,
    resolve_workspace_root,
)

_SCAFFOLD_DATA = {
    "org": "acme",
    "author_name": "Ada",
    "author_email": "ada@example.com",
    "license": "Apache-2.0",
    "description": "A demo member",
}


@pytest.mark.integration
def test_seam_builds_member_data_from_real_workspace(workspace_root: Path) -> None:
    """The seam chain resolves, reads and builds against a real workspace dir."""
    resolved = resolve_workspace_root(workspace_root)
    assert resolved == workspace_root

    workspace_name = read_workspace_name(resolved)
    assert workspace_name == "my-workspace"

    data = build_member_data("axm-foo", workspace_name, _SCAFFOLD_DATA)
    assert data == {
        "member_name": "axm-foo",
        "workspace_name": "my-workspace",
        "description": "A demo member",
        "org": "acme",
        "license": "Apache-2.0",
        "license_holder": "acme",
        "author_name": "Ada",
        "author_email": "ada@example.com",
    }
