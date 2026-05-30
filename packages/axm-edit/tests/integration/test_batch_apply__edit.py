"""Split from ``test_engine.py``."""

from __future__ import annotations

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


class TestMultiLineEdit:
    """Tests for multi-line old/new replacements."""

    def test_multi_line_old(self, tmp_project: Path) -> None:
        """old=`import os\\nimport sys` should match lines 1-2."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(
                        line=1,
                        old="import os\nimport sys",
                        new="import pathlib",
                    ),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert content.startswith("import pathlib\n")
        assert "import os" not in content
        assert "import sys" not in content


class TestFuzzyLineMatching:
    """Tests for fuzzy line-hint search (new behavior)."""

    def test_no_line_auto_search(self, tmp_project: Path) -> None:
        """line=None → searches entire file for `old`."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(old="def hello():", new="def hello(x: int):"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert result.success
        content = (tmp_project / "src" / "foo.py").read_text()
        assert "def hello(x: int):" in content

    def test_ambiguous_old_rejected(self, tmp_project: Path) -> None:
        """old appears multiple times, no line hint → rejected."""
        # Write a file with duplicate content
        (tmp_project / "src" / "dup.py").write_text(
            "x = 1\nx = 1\ny = 2\n",
        )
        ops = [
            ReplaceOp(
                file="src/dup.py",
                edits=[Edit(old="x = 1", new="x = 99")],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("ambiguous" in (d.error or "").lower() for d in result.details)

    def test_old_not_found(self, tmp_project: Path) -> None:
        """old content doesn't exist anywhere → rejected."""
        ops = [
            ReplaceOp(
                file="src/foo.py",
                edits=[
                    Edit(old="NONEXISTENT_CONTENT", new="whatever"),
                ],
            ),
        ]
        result = batch_apply(tmp_project, ops)
        assert not result.success
        assert any("not found" in (d.error or "").lower() for d in result.details)

    def test_multi_file_fuzzy(self, tmp_project: Path) -> None:
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
