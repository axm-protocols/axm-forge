"""Tests for old/new JSON edit parsing and application."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.services.lint import _apply_edits, _fabricates_definition, _parse_edits

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
# Unit tests — _parse_edits
# ---------------------------------------------------------------------------


class TestParseEditsValidJson:
    """Valid JSON array of old/new pairs -> parsed correctly."""

    def test_parse_edits_valid_json(self) -> None:
        raw = '[{"old": "x = 1", "new": "_ = 1"}]'
        result = _parse_edits(raw)
        assert result == [{"old": "x = 1", "new": "_ = 1"}]


class TestParseEditsInvalidJson:
    """Non-JSON text -> empty list."""

    def test_parse_edits_invalid_json(self) -> None:
        result = _parse_edits("not json at all")
        assert result == []


class TestParseEditsMissingKeys:
    """JSON array with missing 'new' key -> empty list."""

    def test_parse_edits_missing_keys(self) -> None:
        raw = '[{"old": "x"}]'
        result = _parse_edits(raw)
        assert result == []


class TestParseEditsStripsFences:
    """Markdown code fences around JSON -> stripped before parsing."""

    def test_parse_edits_strips_fences(self) -> None:
        raw = '```json\n[{"old":"a","new":"b"}]\n```'
        result = _parse_edits(raw)
        assert result == [{"old": "a", "new": "b"}]


# ---------------------------------------------------------------------------
# Unit tests — _apply_edits
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


class TestClaudeWrapsInMarkdown:
    """Output starts with ```json -> stripped before parsing."""

    def test_markdown_fences_stripped(self) -> None:
        raw = '```json\n[{"old": "x", "new": "y"}]\n```'
        result = _parse_edits(raw)
        assert len(result) == 1
        assert result[0] == {"old": "x", "new": "y"}


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


class TestFabricatesDefinition:
    """Detect edits that fabricate a new ``def`` or ``class`` to silence F821/F822."""

    def test_fabricates_def_detected(self) -> None:
        edit = {
            "old": "x = render(items)",
            "new": "def render(items):\n    return ''\n\nx = render(items)",
        }
        assert _fabricates_definition(edit) is True

    def test_fabricates_async_def_detected(self) -> None:
        edit = {"old": "result = fetch()", "new": "async def fetch():\n    ...\n"}
        assert _fabricates_definition(edit) is True

    def test_fabricates_class_detected(self) -> None:
        edit = {"old": "obj = Foo()", "new": "class Foo:\n    pass\n\nobj = Foo()"}
        assert _fabricates_definition(edit) is True

    def test_rename_call_site_not_flagged(self) -> None:
        edit = {"old": "_render(items)", "new": "render(items)"}
        assert _fabricates_definition(edit) is False

    def test_rename_def_in_place_not_flagged(self) -> None:
        edit = {
            "old": "def _render(items):",
            "new": "def render(items):",
        }
        assert _fabricates_definition(edit) is False

    def test_remove_stale_all_entry_not_flagged(self) -> None:
        edit = {"old": '    "_render",\n', "new": ""}
        assert _fabricates_definition(edit) is False


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
