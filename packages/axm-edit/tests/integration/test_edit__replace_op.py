"""Split from ``test_batch_apply_fuzzy_matching.py``."""

from pathlib import Path

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import Edit, ReplaceOp


def test_multi_file_fuzzy(tmp_project: Path) -> None:
    """Fuzzy matching across multiple files in one batch."""
    ops = [
        ReplaceOp(
            file="src/foo.py",
            edits=[
                # Off by 1 — import os is at L1, hint says L2
                Edit(
                    line=2,
                    old="import os",
                    new="import pathlib",
                ),
            ],
        ),
        ReplaceOp(
            file="src/bar.py",
            edits=[
                # No line hint at all
                Edit(old="import foo", new="import baz"),
            ],
        ),
    ]
    result = batch_apply(tmp_project, ops)
    assert result.success
    foo = (tmp_project / "src" / "foo.py").read_text()
    bar = (tmp_project / "src" / "bar.py").read_text()
    assert "import pathlib" in foo
    assert "import baz" in bar
    assert result.summary["modified"] == 2


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
