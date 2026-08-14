"""Integration tests for checkpointing and rolling back rewrite operations.

The rewrite target must be snapshotted like a replaced file, so ``rollback``
restores its pre-batch bytes with no new code path.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.core.checkpoint import create_checkpoint, rollback, snapshot_paths
from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp, RewriteOp

pytestmark = pytest.mark.integration

ORIGINAL = "alpha = 1\nbeta = 2\n"
REWRITTEN = "gamma = 3\n"
OTHER = "delta = 4\n"


def _rewrite(target: Path, content: str) -> RewriteOp:
    """Build a rewrite of *target* checksummed on its current bytes."""
    return RewriteOp(
        op="rewrite",
        file=target.name,
        content=content,
        expected_checksum=hashlib.sha256(target.read_bytes()).hexdigest(),
    )


def test_rewrite_targets_are_snapshotted(tmp_path: Path) -> None:
    """AC4: the rewrite target is captured, so rollback restores its bytes."""
    target = tmp_path / "mod.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    op = _rewrite(target, REWRITTEN)

    assert "mod.py" in list(snapshot_paths(create_checkpoint(tmp_path, [op])))

    result = batch_apply(tmp_path, [op])

    assert result.success is True
    assert target.read_text(encoding="utf-8") == REWRITTEN
    assert result.checkpoint is not None
    assert "mod.py" in list(snapshot_paths(result.checkpoint))
    assert rollback(tmp_path, result.checkpoint).ok is True
    assert target.read_bytes() == ORIGINAL.encode("utf-8")


def test_rollback_restores_a_rewritten_file_after_a_mixed_batch_failure(
    tmp_path: Path,
) -> None:
    """AC4: after rollback the rewrite target is byte-identical to pre-batch."""
    target = tmp_path / "mod.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    other = tmp_path / "other.py"
    other.write_text(OTHER, encoding="utf-8")

    applied = batch_apply(tmp_path, [_rewrite(target, REWRITTEN)])

    assert applied.success is True
    assert applied.checkpoint is not None
    assert target.read_text(encoding="utf-8") == REWRITTEN

    mixed = batch_apply(
        tmp_path,
        [
            _rewrite(target, "epsilon = 5\n"),
            ReplaceOp(
                file="other.py",
                edits=[Edit(old="NO_SUCH_ANCHOR", new="zeta = 6")],
            ),
        ],
    )

    assert mixed.success is False
    assert target.read_text(encoding="utf-8") == REWRITTEN
    assert other.read_text(encoding="utf-8") == OTHER

    assert rollback(tmp_path, applied.checkpoint).ok is True
    assert target.read_bytes() == ORIGINAL.encode("utf-8")
