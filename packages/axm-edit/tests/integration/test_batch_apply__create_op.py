"""Split from ``test_engine.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import CreateOp


class TestCreate:
    """Tests for create operations."""

    def test_create_new_file(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/new.py", content='"""New module."""\n')]
        result = batch_apply(tmp_project, ops)
        assert result.success
        path = tmp_project / "src" / "new.py"
        assert path.exists()
        assert path.read_text() == '"""New module."""\n'
        assert result.summary["created"] == 1

    def test_create_existing_fails(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/foo.py", content="overwrite")]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("already exists" in (d.error or "") for d in result.details)

    def test_create_with_overwrite(self, tmp_project: Path) -> None:
        ops = [
            CreateOp(
                file="src/foo.py",
                content="overwritten\n",
                overwrite=True,
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "foo.py").read_text() == "overwritten\n"

    def test_create_nested_dirs(self, tmp_project: Path) -> None:
        ops = [CreateOp(file="src/auth/__init__.py", content="")]
        result = batch_apply(tmp_project, ops)
        assert result.success
        assert (tmp_project / "src" / "auth" / "__init__.py").exists()
