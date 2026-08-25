from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from axm_ingot.uv.models import Member, ResolvedWorkspace


def test_member_is_frozen() -> None:
    """AC3: Member is a frozen dataclass; mutation raises FrozenInstanceError."""
    member = Member(name="a", path=Path("/x/a"))
    with pytest.raises(FrozenInstanceError):
        member.name = "b"  # type: ignore[misc]


def test_resolved_workspace_holds_members() -> None:
    """AC1, AC3: ResolvedWorkspace carries root + a tuple of members."""
    members = (
        Member(name="a", path=Path("/x/packages/a")),
        Member(name="b", path=Path("/x/packages/b")),
    )
    workspace = ResolvedWorkspace(root=Path("/x"), members=members)
    assert workspace.root == Path("/x")
    assert workspace.members == members
    assert isinstance(workspace.members, tuple)
