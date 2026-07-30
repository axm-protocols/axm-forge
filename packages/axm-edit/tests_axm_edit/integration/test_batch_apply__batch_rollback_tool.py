"""Integration tests wiring the snapshot through batch_apply + BatchRollbackTool.

AXM-1844: the engine snapshots every target path before apply and the
``batch_rollback`` tool restores exactly those paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.checkpoint import create_checkpoint, snapshot_paths
from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp
from axm_edit.tools.batch_rollback import BatchRollbackTool

pytestmark = pytest.mark.integration


def test_batch_rollback_restores_only_touched_paths(tmp_path: Path) -> None:
    """AC2, AC5: rollback reverts touched paths, leaves unrelated dirty files intact."""
    mod = tmp_path / "mod.txt"
    mod.write_text("orig")
    doomed = tmp_path / "doomed.txt"
    doomed.write_text("delete-me")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("untouched")

    ops = [
        ReplaceOp(file="mod.txt", edits=[Edit(old="orig", new="edited")]),
        CreateOp(file="created.txt", content="fresh"),
        DeleteOp(file="doomed.txt"),
    ]

    result = batch_apply(tmp_path, ops)
    assert result.success is True
    assert result.checkpoint is not None
    assert (tmp_path / "created.txt").exists()
    assert not doomed.exists()
    assert mod.read_text().rstrip("\n") == "edited"

    tool = BatchRollbackTool()
    out = tool.execute(path=str(tmp_path), checkpoint=result.checkpoint)
    assert out.success is True

    # Touched paths reverted.
    assert mod.read_text() == "orig"
    assert not (tmp_path / "created.txt").exists()
    assert doomed.exists()
    assert doomed.read_text() == "delete-me"
    # Unrelated dirty file untouched.
    assert unrelated.read_text() == "untouched"


def test_rollback_missing_checkpoint_fails(tmp_path: Path) -> None:
    """batch_rollback with no checkpoint fails with a readable error."""
    out = BatchRollbackTool().execute(path=str(tmp_path))
    assert out.success is False
    assert out.error is not None
    assert "checkpoint" in out.error.lower()


def test_rollback_malformed_checkpoint_fails(tmp_path: Path) -> None:
    """A malformed (non-JSON) checkpoint fails without touching the tree."""
    out = BatchRollbackTool().execute(path=str(tmp_path), checkpoint="not-json")
    assert out.success is False
    assert out.error is not None
    assert "rollback failed" in out.error.lower()


def test_rollback_non_directory_root_fails(tmp_path: Path) -> None:
    """A root that is not a directory fails with a readable error."""
    missing = tmp_path / "nope"
    out = BatchRollbackTool().execute(path=str(missing), checkpoint='{"entries": {}}')
    assert out.success is False
    assert out.error is not None
    assert "directory" in out.error.lower()


def test_traversal_path_is_snapshotted(tmp_path: Path) -> None:
    """Regression (P1-1): a ``..`` path the engine accepts is also captured.

    The engine's resolver accepts ``sub/../a.py`` (it resolves back inside
    root); the checkpoint resolver once rejected any ``..`` segment, so such
    a file was applied but never snapshotted — a failed batch could not
    restore it. With the unified resolver the snapshot now captures it under
    its canonical key, closing the rollback hole.
    """
    sub = tmp_path / "sub"
    sub.mkdir()
    target = tmp_path / "a.py"
    target.write_text("ORIGINAL\n")

    checkpoint = create_checkpoint(
        tmp_path,
        [ReplaceOp(file="sub/../a.py", edits=[Edit(old="ORIGINAL", new="MUTATED")])],
    )

    # The traversal spelling resolves to a.py and IS captured (canonical key).
    assert "a.py" in snapshot_paths(checkpoint)


def test_traversal_path_rolled_back_on_mid_apply_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (P1-1): a ``..``-spelled file is restored when apply aborts.

    op1 mutates ``sub/../a.py`` (resolves to a.py) and applies; op2's target
    write is forced to raise mid-apply, triggering rollback. Because the
    unified resolver captured a.py, rollback restores it — previously the
    divergent checkpoint filter left a.py mutated.
    """
    sub = tmp_path / "sub"
    sub.mkdir()
    a = tmp_path / "a.py"
    a.write_text("ORIGINAL\n")
    b = tmp_path / "b.py"
    b.write_text("ANCHOR\n")

    ops = [
        ReplaceOp(file="sub/../a.py", edits=[Edit(old="ORIGINAL", new="MUTATED")]),
        ReplaceOp(file="b.py", edits=[Edit(old="ANCHOR", new="CHANGED")]),
    ]

    # Force a mid-apply OSError on b.py's write via the stdlib boundary
    # (public seam) — a.py is applied first, then op2's write raises and
    # triggers rollback.
    real_write_text = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.name == "b.py":
            msg = "forced mid-apply failure"
            raise OSError(msg)
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    result = batch_apply(tmp_path, ops)

    assert result.success is False
    assert result.rollback_failed is False
    # a.py restored to its pre-batch bytes — the hole is closed.
    assert a.read_text() == "ORIGINAL\n"


def test_empty_new_deletes_matched_lines(tmp_path: Path) -> None:
    """Regression (P2-2): ``new=""`` removes the block, not leaving a blank line."""
    target = tmp_path / "f.txt"
    target.write_text("keep\nremove-me\ntail\n")

    result = batch_apply(
        tmp_path,
        [ReplaceOp(file="f.txt", edits=[Edit(old="remove-me", new="")])],
    )

    assert result.success is True
    # The middle line is gone with no residual empty line.
    assert target.read_text() == "keep\ntail\n"


def test_delete_directory_rejected(tmp_path: Path) -> None:
    """Regression (P2-6): deleting a directory is rejected at validation."""
    (tmp_path / "adir").mkdir()

    result = batch_apply(tmp_path, [DeleteOp(file="adir")])

    assert result.success is False
    assert result.error is not None
    # Directory still there — nothing was touched.
    assert (tmp_path / "adir").is_dir()
