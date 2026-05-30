"""Tests for old/new JSON edit parsing and fabrication detection."""

from __future__ import annotations

import pytest

from axm_edit.services.lint import fabricates_definition, parse_edits

# ---------------------------------------------------------------------------
# Unit tests — parse_edits
# ---------------------------------------------------------------------------


class TestParseEdits:
    """parse_edits maps raw output to a list of old/new pairs."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param(
                '[{"old": "x = 1", "new": "_ = 1"}]',
                [{"old": "x = 1", "new": "_ = 1"}],
                id="valid_json",
            ),
            pytest.param("not json at all", [], id="invalid_json"),
            pytest.param('[{"old": "x"}]', [], id="missing_keys"),
            pytest.param(
                '```json\n[{"old":"a","new":"b"}]\n```',
                [{"old": "a", "new": "b"}],
                id="strips_fences",
            ),
        ],
    )
    def test_parse_edits(self, raw: str, expected: list[dict[str, str]]) -> None:
        assert parse_edits(raw) == expected


class TestClaudeWrapsInMarkdown:
    """Output starts with ```json -> stripped before parsing."""

    def test_markdown_fences_stripped(self) -> None:
        raw = '```json\n[{"old": "x", "new": "y"}]\n```'
        result = parse_edits(raw)
        assert len(result) == 1
        assert result[0] == {"old": "x", "new": "y"}


class TestFabricatesDefinition:
    """Detect edits that fabricate a new ``def`` or ``class`` to silence F821/F822."""

    @pytest.mark.parametrize(
        ("edit", "expected"),
        [
            pytest.param(
                {
                    "old": "x = render(items)",
                    "new": "def render(items):\n    return ''\n\nx = render(items)",
                },
                True,
                id="def_detected",
            ),
            pytest.param(
                {"old": "result = fetch()", "new": "async def fetch():\n    ...\n"},
                True,
                id="async_def_detected",
            ),
            pytest.param(
                {"old": "obj = Foo()", "new": "class Foo:\n    pass\n\nobj = Foo()"},
                True,
                id="class_detected",
            ),
            pytest.param(
                {"old": "_render(items)", "new": "render(items)"},
                False,
                id="rename_call_site_not_flagged",
            ),
            pytest.param(
                {"old": "def _render(items):", "new": "def render(items):"},
                False,
                id="rename_def_in_place_not_flagged",
            ),
            pytest.param(
                {"old": '    "_render",\n', "new": ""},
                False,
                id="remove_stale_all_entry_not_flagged",
            ),
        ],
    )
    def test_fabrication_verdict(self, edit: dict[str, str], expected: bool) -> None:
        assert fabricates_definition(edit) is expected
