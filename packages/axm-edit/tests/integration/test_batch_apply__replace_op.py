"""Split from ``test_engine.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp


class TestSingleReplace:
    """Tests for single-file replace operations."""

    @pytest.mark.parametrize(
        "line",
        [
            pytest.param(1, id="exact_line"),
            pytest.param(2, id="off_by_one"),
            pytest.param(6, id="off_by_five"),
            pytest.param(None, id="no_line_auto_search"),
        ],
    )
    def test_single_import_replace_by_line_hint(
        self, tmp_project: Path, line: int | None
    ) -> None:
        """Replacing `import os` succeeds for exact/fuzzy/no line hints."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[Edit(line=line, old="import os", new="import pathlib")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import os" not in content

    def test_multiple_edits_same_file(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                    Edit(line=2, old="import sys", new="import json"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import json" in content
        assert result.summary["modified"] == 1

    def test_old_mismatch_fails(self, tmp_project: Path) -> None:
        """If `old` doesn't match file content, nothing is touched."""
        original = (tmp_project / "src" / "foo.py").read_text()
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[Edit(line=1, old="WRONG", new="import pathlib")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert result.error == "Validation failed"
        assert len(result.details) >= 1
        # File must be untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original

    def test_file_not_found_fails(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="nope.py",
                edits=[Edit(line=1, old="a", new="b")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "") for d in result.details)


class TestOverlap:
    """Tests for overlapping edit detection."""

    def test_overlapping_edits_rejected(self, tmp_project: Path) -> None:
        original = (tmp_project / "src" / "foo.py").read_text()
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os\nimport sys",
                        new="x",
                    ),
                    Edit(line=2, old="import sys", new="y"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        # File untouched
        assert (tmp_project / "src" / "foo.py").read_text() == original


class TestMergeSameFile:
    """Tests for merging edits from multiple ReplaceOps."""

    def test_two_replace_ops_same_file(self, tmp_project: Path) -> None:
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=1, old="import os", new="import pathlib"),
                ],
            ),
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(line=2, old="import sys", new="import json"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert "import json" in content
        # Merged into 1 file modification
        assert result.summary["modified"] == 1
