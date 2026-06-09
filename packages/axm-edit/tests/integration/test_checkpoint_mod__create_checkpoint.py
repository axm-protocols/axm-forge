"""Integration test proving checkpoint/rollback issue no global git commands.

Exercises the module-public ``create_checkpoint`` / ``rollback`` pair and
asserts no subprocess (git checkout/clean/stash) is invoked (AXM-1844).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core import checkpoint as checkpoint_mod
from axm_edit.core.checkpoint import create_checkpoint, rollback
from axm_edit.models.operations import Edit, ReplaceOp

pytestmark = pytest.mark.integration


def test_no_git_global_commands_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No global git checkout/clean/stash is invoked by checkpoint/rollback."""
    calls: list[list[str]] = []

    def _spy(cmd: list[str], *args: object, **kwargs: object) -> object:
        calls.append(list(cmd))
        raise AssertionError(f"subprocess invoked: {cmd}")

    monkeypatch.setattr(checkpoint_mod.subprocess, "run", _spy)

    target = tmp_path / "f.txt"
    target.write_text("v1")
    ops = [ReplaceOp(file="f.txt", edits=[Edit(old="v1", new="v2")])]

    snapshot = create_checkpoint(tmp_path, ops)
    target.write_text("v2")
    rollback(tmp_path, snapshot)

    assert calls == []
