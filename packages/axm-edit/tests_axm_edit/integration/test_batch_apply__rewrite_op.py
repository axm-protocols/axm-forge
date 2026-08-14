"""Integration tests for the rewrite operation applied by ``batch_apply``.

Every case runs against a real ``tmp_path`` tree and observes bytes on disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import BatchResult, RewriteOp
from axm_edit.utils import is_binary, resolve_safe

pytestmark = pytest.mark.integration

ORIGINAL = "alpha = 1\nbeta = 2\n"
REWRITTEN = "gamma = 3\n"


def _digest(data: bytes) -> str:
    """Return the digest carried by ``expected_checksum`` for *data*."""
    return hashlib.sha256(data).hexdigest()


def _rewrite(file: str, content: str, checksum: str) -> RewriteOp:
    """Build a rewrite operation targeting *file*."""
    return RewriteOp(
        op="rewrite",
        file=file,
        content=content,
        expected_checksum=checksum,
    )


def _messages(result: BatchResult) -> str:
    """Flatten every diagnostic string carried by *result*."""
    return " ".join([result.error or "", *(d.error or "" for d in result.details)])


def test_matching_checksum_rewrites_the_whole_file(tmp_path: Path) -> None:
    """AC1: a rewrite whose checksum matches replaces the file bytes exactly."""
    target = tmp_path / "mod.py"
    target.write_text(ORIGINAL, encoding="utf-8")

    result = batch_apply(
        tmp_path,
        [_rewrite("mod.py", REWRITTEN, _digest(target.read_bytes()))],
    )

    assert result.success is True
    assert target.read_bytes() == REWRITTEN.encode("utf-8")
    assert result.applied >= 1
    assert sum(result.summary.values()) >= 1


def test_missing_target_is_refused(tmp_path: Path) -> None:
    """AC2: a rewrite of an absent file is refused and creates nothing."""
    result = batch_apply(
        tmp_path,
        [_rewrite("ghost.py", REWRITTEN, _digest(ORIGINAL.encode("utf-8")))],
    )

    assert result.success is False
    assert "rewrite_target_missing" in _messages(result)
    assert list(tmp_path.iterdir()) == []


def test_symlink_target_is_refused(tmp_path: Path) -> None:
    """AC2: a symlink target is not a regular file, so the rewrite is refused."""
    real = tmp_path / "real.py"
    real.write_text(ORIGINAL, encoding="utf-8")
    link = tmp_path / "link.py"
    link.symlink_to(real)

    result = batch_apply(
        tmp_path,
        [_rewrite("link.py", REWRITTEN, _digest(real.read_bytes()))],
    )

    assert result.success is False
    assert "rewrite_target_not_regular" in _messages(result)
    assert real.read_text(encoding="utf-8") == ORIGINAL
    assert link.is_symlink()


def test_directory_target_is_refused(tmp_path: Path) -> None:
    """AC2: a directory target is not a regular file, so the rewrite is refused."""
    (tmp_path / "pkg").mkdir()

    result = batch_apply(
        tmp_path,
        [_rewrite("pkg", REWRITTEN, _digest(ORIGINAL.encode("utf-8")))],
    )

    assert result.success is False
    assert "rewrite_target_not_regular" in _messages(result)
    assert (tmp_path / "pkg").is_dir()


def test_stale_checksum_is_refused_before_mutation(tmp_path: Path) -> None:
    """AC3: a checksum stale w.r.t. the current bytes is refused, bytes intact."""
    target = tmp_path / "mod.py"
    target.write_text(ORIGINAL, encoding="utf-8")
    stale = _digest(target.read_bytes())
    drifted = "alpha = 99\n"
    target.write_text(drifted, encoding="utf-8")

    result = batch_apply(tmp_path, [_rewrite("mod.py", REWRITTEN, stale)])

    assert result.success is False
    assert "rewrite_checksum_stale" in _messages(result)
    assert target.read_text(encoding="utf-8") == drifted


def test_binary_target_is_refused(tmp_path: Path) -> None:
    """AC5: a binary target is refused and keeps every original byte."""
    target = tmp_path / "blob.bin"
    payload = b"\x00\x01\x02binary\x00payload"
    target.write_bytes(payload)
    assert is_binary(target) is True

    result = batch_apply(
        tmp_path,
        [_rewrite("blob.bin", REWRITTEN, _digest(payload))],
    )

    assert result.success is False
    assert result.details != []
    assert target.read_bytes() == payload


def test_out_of_root_target_is_refused(tmp_path: Path) -> None:
    """AC5: a rewrite escaping the batch root is refused, outside file intact."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text(ORIGINAL, encoding="utf-8")
    assert resolve_safe(root, "../outside.py") is None

    result = batch_apply(
        root,
        [_rewrite("../outside.py", REWRITTEN, _digest(outside.read_bytes()))],
    )

    assert result.success is False
    assert result.details != []
    assert outside.read_text(encoding="utf-8") == ORIGINAL
