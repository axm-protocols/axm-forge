"""Integration tests for applying old/new JSON edits to real files."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.services.lint import _apply_edits

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def src_file(tmp_path: Path) -> Path:
    """A simple Python source file for edit tests."""
    f = tmp_path / "example.py"
    f.write_text("x = 1\ny = 2\n")
    return f


# ---------------------------------------------------------------------------
# Integration tests — _apply_edits
# ---------------------------------------------------------------------------


class TestApplyEditsReplace:
    """old text found -> replaced with new text."""

    def test_apply_edits_replace(self, src_file: Path) -> None:
        edits = [{"old": "x = 1", "new": "_ = 1"}]
        result = _apply_edits(src_file, edits)
        assert result is True
        assert src_file.read_text() == "_ = 1\ny = 2\n"


class TestApplyEditsInsert:
    """old is anchor text, new is anchor + extra lines -> insertion."""

    def test_apply_edits_insert(self, tmp_path: Path) -> None:
        f = tmp_path / "ins.py"
        f.write_text("import os\n\ndef f(): pass")
        edits = [{"old": "import os", "new": "import os\nimport logging"}]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert "import logging" in content


class TestApplyEditsDelete:
    """old is block to remove, new is empty -> deletion."""

    def test_apply_edits_delete(self, tmp_path: Path) -> None:
        f = tmp_path / "del.py"
        f.write_text("import os\nimport sys\nx = 1")
        edits = [{"old": "import sys\n", "new": ""}]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert "import sys" not in content
        assert "import os" in content
        assert "x = 1" in content


class TestApplyEditsNoMatch:
    """old text not in file -> file unchanged, returns False."""

    def test_apply_edits_no_match(self, src_file: Path) -> None:
        original = src_file.read_text()
        edits = [{"old": "nonexistent text", "new": "replacement"}]
        result = _apply_edits(src_file, edits)
        assert result is False
        assert src_file.read_text() == original


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEmptyJsonArray:
    """Claude returns [] -> no changes, no error."""

    def test_empty_array(self, src_file: Path) -> None:
        original = src_file.read_text()
        edits: list[dict[str, str]] = []
        result = _apply_edits(src_file, edits)
        assert result is False
        assert src_file.read_text() == original


class TestOldMatchesMultipleTimes:
    """old appears 3 times -> only first occurrence replaced."""

    def test_first_occurrence_only(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.py"
        f.write_text("pass\npass\npass\n")
        edits = [{"old": "pass", "new": "return"}]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert content.count("return") == 1
        assert content.count("pass") == 2


class TestNewlineDifferences:
    r"""old has \n, file has \r\n -> normalize before matching."""

    def test_crlf_normalization(self, tmp_path: Path) -> None:
        f = tmp_path / "crlf.py"
        f.write_text("x = 1\r\ny = 2\r\n")
        edits = [{"old": "x = 1", "new": "_ = 1"}]
        result = _apply_edits(f, edits)
        assert result is True
        assert "_ = 1" in f.read_text()


class TestVeryLargeJsonOutput:
    """Claude returns 50+ edits -> all applied sequentially."""

    def test_large_edit_list(self, tmp_path: Path) -> None:
        # Build a file with 50 unique lines
        lines = [f"var_{i} = {i}" for i in range(50)]
        f = tmp_path / "big.py"
        f.write_text("\n".join(lines) + "\n")

        # Build 50 edits
        edits = [
            {"old": f"var_{i} = {i}", "new": f"var_{i} = {i * 10}"} for i in range(50)
        ]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        for i in range(50):
            assert f"var_{i} = {i * 10}" in content


class TestInsertEditApplied:
    """JSON with insert (old=anchor, new=anchor+new lines) -> file updated."""

    def test_insert_edit(self, tmp_path: Path) -> None:
        f = tmp_path / "insert.py"
        f.write_text("def main():\n    print('hello')\n")
        edits = [
            {
                "old": "def main():\n    print('hello')",
                "new": "def main():\n    logging.info('start')\n    print('hello')",
            }
        ]
        result = _apply_edits(f, edits)
        assert result is True
        assert "logging.info('start')" in f.read_text()


class TestDeleteEditApplied:
    """JSON with delete (old=block, new="") -> lines removed."""

    def test_delete_edit(self, tmp_path: Path) -> None:
        f = tmp_path / "delete.py"
        f.write_text("import os\nimport sys\nimport json\n\nx = 1\n")
        edits = [{"old": "import sys\n", "new": ""}]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert "import sys" not in content
        assert "import os" in content
        assert "import json" in content


class TestMultilineReplace:
    """old spans 2 lines, new spans 3 lines -> correct replacement."""

    def test_multiline_replace(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.py"
        f.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        edits = [
            {
                "old": "except:\n    pass",
                "new": "except Exception as e:\n    logging.error(e)\n    raise",
            }
        ]
        result = _apply_edits(f, edits)
        assert result is True
        content = f.read_text()
        assert "except Exception as e:" in content
        assert "logging.error(e)" in content
        assert "raise" in content
