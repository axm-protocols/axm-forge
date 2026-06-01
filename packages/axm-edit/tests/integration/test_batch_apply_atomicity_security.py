"""Split from ``test_engine.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import (
    CreateOp,
    DeleteOp,
    Edit,
    Operation,
    ReplaceOp,
)


class TestMixedOperations:
    """Tests for mixed operation batches."""

    def test_replace_create_delete(self, tmp_project: Path) -> None:
        ops: list[Operation] = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            CreateOp(file="src/new.py", content='"""new."""\n'),
            DeleteOp(file="README.md"),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert result.applied == 3  # 1 edit + 1 create + 1 delete
        assert result.summary == {
            "modified": 1,
            "created": 1,
            "deleted": 1,
        }
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert (tmp_project / "src" / "new.py").exists()
        assert not (tmp_project / "README.md").exists()


class TestSecurity:
    """Tests for security constraints."""

    def test_path_traversal_rejected(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="../etc/passwd", content="hacked")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("traversal" in (d.error or "").lower() for d in result.details)

    def test_path_traversal_in_replace(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="../etc/passwd",
                edits=[Edit(line=1, old="a", new="b")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success

    def test_path_traversal_in_delete(self, tmp_project: Path) -> None:
        ops = [DeleteOp(file="../etc/passwd")]
        result = batch_apply(tmp_project, ops)
        assert not result.success


class TestAtomicity:
    """Tests that partial failures leave the project untouched."""

    def test_valid_and_invalid_mix(self, tmp_project: Path) -> None:
        """One valid + one invalid operation → nothing applied."""
        original_foo = (tmp_project / "src" / "foo.py").read_text()
        ops: list[Operation] = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            DeleteOp(file="nonexistent.py"),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        # foo.py must be untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original_foo
