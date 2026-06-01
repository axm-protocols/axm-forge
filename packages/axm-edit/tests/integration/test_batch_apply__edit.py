"""Split from ``test_batch_apply_fuzzy_matching.py``."""

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp


class TestBottomToTop:
    """Tests for bottom-to-top edit ordering."""

    def test_adding_lines_doesnt_shift_upper(self, tmp_project: Path) -> None:
        """Edit at line 4 adds lines; edit at line 1 still works."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os",
                        new="import os\nimport pathlib",
                    ),
                    Edit(
                        line=4,
                        old="def hello():",
                        new='def hello(name: str = "world"):',
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "import pathlib" in content
        assert 'def hello(name: str = "world"):' in content


def test_multiple_edits_same_file(tmp_project: Path) -> None:
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
