"""Split from ``test_engine.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import DeleteOp


class TestDelete:
    """Tests for delete operations."""

    def test_delete_file(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="README.md")]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert not (tmp_project / "README.md").exists()
        assert result.summary["deleted"] == 1

    def test_delete_missing_fails(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="nonexistent.py")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "") for d in result.details)


def test_path_traversal_in_delete(tmp_project: Path) -> None:
    ops = [DeleteOp(file="../etc/passwd")]
    result = batch_apply(tmp_project, ops)
    assert not result.success
