"""Tests for old/new JSON edit parsing and fabrication detection."""

from __future__ import annotations

from axm_edit.services.lint import fabricates_definition, parse_edits

# ---------------------------------------------------------------------------
# Unit tests — parse_edits
# ---------------------------------------------------------------------------


class TestParseEditsValidJson:
    """Valid JSON array of old/new pairs -> parsed correctly."""

    def test_parse_edits_valid_json(self) -> None:
        raw = '[{"old": "x = 1", "new": "_ = 1"}]'
        result = parse_edits(raw)
        assert result == [{"old": "x = 1", "new": "_ = 1"}]


class TestParseEditsInvalidJson:
    """Non-JSON text -> empty list."""

    def test_parse_edits_invalid_json(self) -> None:
        result = parse_edits("not json at all")
        assert result == []


class TestParseEditsMissingKeys:
    """JSON array with missing 'new' key -> empty list."""

    def test_parse_edits_missing_keys(self) -> None:
        raw = '[{"old": "x"}]'
        result = parse_edits(raw)
        assert result == []


class TestParseEditsStripsFences:
    """Markdown code fences around JSON -> stripped before parsing."""

    def test_parse_edits_strips_fences(self) -> None:
        raw = '```json\n[{"old":"a","new":"b"}]\n```'
        result = parse_edits(raw)
        assert result == [{"old": "a", "new": "b"}]


class TestClaudeWrapsInMarkdown:
    """Output starts with ```json -> stripped before parsing."""

    def test_markdown_fences_stripped(self) -> None:
        raw = '```json\n[{"old": "x", "new": "y"}]\n```'
        result = parse_edits(raw)
        assert len(result) == 1
        assert result[0] == {"old": "x", "new": "y"}


class TestFabricatesDefinition:
    """Detect edits that fabricate a new ``def`` or ``class`` to silence F821/F822."""

    def test_fabricates_def_detected(self) -> None:
        edit = {
            "old": "x = render(items)",
            "new": "def render(items):\n    return ''\n\nx = render(items)",
        }
        assert fabricates_definition(edit) is True

    def test_fabricates_async_def_detected(self) -> None:
        edit = {"old": "result = fetch()", "new": "async def fetch():\n    ...\n"}
        assert fabricates_definition(edit) is True

    def test_fabricates_class_detected(self) -> None:
        edit = {"old": "obj = Foo()", "new": "class Foo:\n    pass\n\nobj = Foo()"}
        assert fabricates_definition(edit) is True

    def test_rename_call_site_not_flagged(self) -> None:
        edit = {"old": "_render(items)", "new": "render(items)"}
        assert fabricates_definition(edit) is False

    def test_rename_def_in_place_not_flagged(self) -> None:
        edit = {
            "old": "def _render(items):",
            "new": "def render(items):",
        }
        assert fabricates_definition(edit) is False

    def test_remove_stale_all_entry_not_flagged(self) -> None:
        edit = {"old": '    "_render",\n', "new": ""}
        assert fabricates_definition(edit) is False
