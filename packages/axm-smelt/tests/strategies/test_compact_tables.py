from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.compact_tables import CompactTablesStrategy


@pytest.fixture
def strategy() -> CompactTablesStrategy:
    return CompactTablesStrategy()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestCompactTablesUnit:
    def test_compact_padded_cells(self, strategy: CompactTablesStrategy) -> None:
        ctx = SmeltContext(text="| foo  |  bar  |", format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == "|foo|bar|"

    def test_compact_separator_row(self, strategy: CompactTablesStrategy) -> None:
        ctx = SmeltContext(text="| --- | --- |", format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == "|---|---|"

    def test_preserve_alignment_markers(self, strategy: CompactTablesStrategy) -> None:
        ctx = SmeltContext(text="| :---: | ---: |", format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == "|:---:|---:|"

    def test_passthrough_non_table(self, strategy: CompactTablesStrategy) -> None:
        text = "Regular paragraph text"
        ctx = SmeltContext(text=text, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == text

    def test_name_and_category(self, strategy: CompactTablesStrategy) -> None:
        assert strategy.name == "compact_tables"
        assert strategy.category == "whitespace"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestCompactTablesFunctional:
    def test_compact_real_table(self, strategy: CompactTablesStrategy) -> None:
        table = (
            "| Name  | Age | City    |\n"
            "| ----- | --- | ------- |\n"
            "| Alice | 30  | Paris   |\n"
            "| Bob   | 25  | London  |"
        )
        ctx = SmeltContext(text=table, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        lines = result.text.split("\n")
        assert lines[0] == "|Name|Age|City|"
        assert lines[1] == "|-----|---|-------|"
        assert lines[2] == "|Alice|30|Paris|"
        assert lines[3] == "|Bob|25|London|"

    def test_compact_mixed_content(self, strategy: CompactTablesStrategy) -> None:
        text = (
            "# Title\n"
            "\n"
            "Some paragraph.\n"
            "\n"
            "| Col1 | Col2 |\n"
            "| ---- | ---- |\n"
            "| a    | b    |\n"
            "\n"
            "Another paragraph.\n"
        )
        ctx = SmeltContext(text=text, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        lines = result.text.split("\n")
        assert lines[0] == "# Title"
        assert lines[2] == "Some paragraph."
        assert lines[4] == "|Col1|Col2|"
        assert lines[5] == "|----|----|"
        assert lines[6] == "|a|b|"
        assert lines[8] == "Another paragraph."


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCompactTablesEdgeCases:
    def test_already_compact_table(self, strategy: CompactTablesStrategy) -> None:
        text = "|foo|bar|\n|---|---|\n|a|b|"
        ctx = SmeltContext(text=text, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result is ctx  # noop — same object returned

    def test_single_column_table(self, strategy: CompactTablesStrategy) -> None:
        ctx = SmeltContext(text="| value |", format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == "|value|"

    def test_empty_cells(self, strategy: CompactTablesStrategy) -> None:
        ctx = SmeltContext(text="|  |  |", format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == "||"

    def test_pipe_in_code_span(self, strategy: CompactTablesStrategy) -> None:
        text = "Some text with `|pipe|` inside"
        ctx = SmeltContext(text=text, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert result.text == text

    def test_table_inside_fenced_code(self, strategy: CompactTablesStrategy) -> None:
        text = "```\n| foo | bar |\n| --- | --- |\n```"
        ctx = SmeltContext(text=text, format=Format.MARKDOWN)
        result = strategy.apply(ctx)
        assert "| foo | bar |" in result.text  # padding preserved inside code block

    def test_non_markdown_format_passthrough(
        self, strategy: CompactTablesStrategy
    ) -> None:
        text = "| foo  |  bar  |"
        ctx = SmeltContext(text=text, format=Format.TEXT)
        result = strategy.apply(ctx)
        assert result is ctx  # unchanged for non-markdown

    def test_registered_in_registry(self) -> None:
        from axm_smelt.strategies import _REGISTRY

        assert "compact_tables" in _REGISTRY
