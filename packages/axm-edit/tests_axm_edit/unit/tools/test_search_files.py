"""Tests for axm_edit.tools.search_files — SearchFilesTool."""

from __future__ import annotations

import tiktoken

from axm_edit.tools.search_files import (
    SearchFilesTool,
    render_text,
    truncate_line,
)


def _high_duplication_matches() -> list[dict[str, object]]:
    contents = [
        (
            "def resolve_runtime_backend(configuration: RuntimeConfiguration, *, "
            "strict: bool = True) -> Backend:"
        ),
        (
            "class DurableJournalWriter(AppendOnlyWriter[RunEvent], SupportsFlush, "
            "Protocol):"
        ),
        (
            "async def persist_checkpoint(session_id: str, "
            "payload: Mapping[str, object]) -> None:"
        ),
        (
            "result = await executor.execute(node=node, context=context, "
            "retry_policy=retry_policy)"
        ),
        (
            "return ToolResult(success=True, data=serialized_payload, "
            "text=compact_rendering)"
        ),
        (
            "with transaction.atomic(isolation_level=IsolationLevel.SERIALIZABLE) "
            "as transaction:"
        ),
        (
            'raise ConfigurationError(f"Unsupported backend {backend_name!r} '
            'f"for profile {profile_name!r}")'
        ),
        (
            "metadata: dict[str, JsonValue] = normalize_metadata(event.metadata, "
            "schema=EVENT_SCHEMA)"
        ),
    ]
    return [
        {
            "file": f"src/service_{index % 13:02d}.py",
            "line": 40 + index * 7,
            "content": contents[index % len(contents)],
        }
        for index in range(26)
    ]


class TestSearchFilesTool:
    """Tests for the SearchFilesTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = SearchFilesTool()
        assert tool.name == "search_files"

    def test_bad_root(self) -> None:
        """Non-existent root directory returns error."""
        result = SearchFilesTool().execute(path="/nonexistent/root", pattern="foo")
        assert result.success is False
        assert "not a directory" in (result.error or "").lower()

    def test_missing_pattern_yields_actionable_hint_text(self) -> None:
        """AC1: missing pattern text names the required ``pattern=`` argument."""
        result = SearchFilesTool().execute(pattern=None)

        assert result.text
        hint_lines = [
            line for line in result.text.splitlines() if line.startswith("hint:")
        ]
        assert hint_lines
        assert "pattern=" in hint_lines[0]


class TestRenderText:
    """Tests for the ``render_text`` compact rendering helper."""

    def test_zero_matches(self) -> None:
        assert render_text(matches=[], count=0, truncated=False) == (
            "search_files | 0 matches"
        )

    def test_truncation_flag_is_surfaced(self) -> None:
        """The TRUNCATED signal must appear in the text when the cap is hit."""
        matches: list[dict[str, object]] = [
            {"file": "a.py", "line": 1, "content": "hit"}
        ]
        text = render_text(matches=matches, count=1, truncated=True)
        assert "TRUNCATED at 1" in text

    def test_singular_match_and_file(self) -> None:
        matches: list[dict[str, object]] = [
            {"file": "a.py", "line": 7, "content": "needle"}
        ]
        text = render_text(matches=matches, count=1, truncated=False)
        assert text == "search_files | 1 match · 1 file\na.py\n  7: needle"

    def test_high_duplication_is_grouped_by_content(self) -> None:
        """AC1: 26 sites over 8 contents render each content once without loss."""
        matches = _high_duplication_matches()

        text = render_text(matches=matches, count=len(matches), truncated=False)

        distinct_contents = {str(match["content"]) for match in matches}
        assert len(distinct_contents) == 8
        assert all(text.count(content) == 1 for content in distinct_contents)
        assert all(f"{match['file']}:{match['line']}" in text for match in matches)

    def test_high_duplication_stays_under_token_budget(self) -> None:
        """AC2: the content-grouped 26/8 rendering uses fewer than 500 tokens."""
        matches = _high_duplication_matches()

        text = render_text(matches=matches, count=len(matches), truncated=False)
        token_count = len(tiktoken.get_encoding("o200k_base").encode(text))

        assert token_count < 500


class TestTruncateLine:
    """Per-line content capping (AC1, AC2)."""

    def test_long_line_truncated_with_marker(self) -> None:
        """A line over the cap is clipped and carries a truncation marker."""
        original = "x" * 5000
        out = truncate_line(original)
        assert len(out) < len(original)
        assert len(out) <= 500 + 80
        assert out.startswith("x" * 500)
        assert "[truncated:" in out
        assert out.endswith("]")

    def test_short_line_unchanged(self) -> None:
        """A line at or under the cap is returned verbatim, with no marker."""
        original = "def hello():  # a short matching line"
        out = truncate_line(original)
        assert out == original
        assert "truncated" not in out
