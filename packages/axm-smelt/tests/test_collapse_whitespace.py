from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.collapse_whitespace import CollapseWhitespaceStrategy


@pytest.fixture
def strategy() -> CollapseWhitespaceStrategy:
    return CollapseWhitespaceStrategy()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_collapse_multiple_blanks(strategy: CollapseWhitespaceStrategy) -> None:
    """3+ consecutive blank lines reduced to single blank line."""
    text = "line1\n\n\n\nline2\n\n\n\n\nline3"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert result.text == "line1\n\nline2\n\nline3"


def test_strip_trailing_spaces(strategy: CollapseWhitespaceStrategy) -> None:
    """Lines ending with spaces/tabs have trailing whitespace removed."""
    text = "hello   \nworld\t\t\nfoo  \t \n"
    ctx = SmeltContext(text=text, format=Format.TEXT)
    result = strategy.apply(ctx)
    for line in result.text.split("\n"):
        assert line == line.rstrip(), f"Trailing whitespace found: {line!r}"


def test_preserve_code_blocks(strategy: CollapseWhitespaceStrategy) -> None:
    """Fenced code block with intentional blank lines is unchanged."""
    code_block = "```python\ndef foo():\n\n\n\n    pass\n```"
    text = f"before\n\n\n\n{code_block}\n\n\n\nafter"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert code_block in result.text


def test_name_and_category(strategy: CollapseWhitespaceStrategy) -> None:
    """Strategy name and category are correct."""
    assert strategy.name == "collapse_whitespace"
    assert strategy.category == "whitespace"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_collapse_real_markdown(strategy: CollapseWhitespaceStrategy) -> None:
    """CLAUDE.md-style content with excessive whitespace is compacted."""
    text = (
        "# Heading\n"
        "\n"
        "\n"
        "\n"
        "Some paragraph with trailing spaces.   \n"
        "\n"
        "\n"
        "\n"
        "\n"
        "## Subheading\n"
        "\n"
        "\n"
        "\n"
        "- item 1  \n"
        "- item 2\t\n"
        "\n"
        "\n"
        "\n"
        "End\n"
    )
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    # Token count reduced: result is shorter
    assert len(result.text) < len(text)
    # Structure preserved: headings and items still present
    assert "# Heading" in result.text
    assert "## Subheading" in result.text
    assert "- item 1" in result.text
    assert "- item 2" in result.text


def test_collapse_noop_json(strategy: CollapseWhitespaceStrategy) -> None:
    """JSON input with Format.JSON returns ctx unchanged."""
    text = '{"key":   "value"\n\n\n}'
    ctx = SmeltContext(text=text, format=Format.JSON)
    result = strategy.apply(ctx)
    assert result is ctx


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_multiple_code_blocks(strategy: CollapseWhitespaceStrategy) -> None:
    """Only blanks outside code blocks are collapsed."""
    block1 = "```\ncode1\n\n\n\ncode1end\n```"
    block2 = "```\ncode2\n\n\n\ncode2end\n```"
    text = f"intro\n\n\n\n{block1}\n\n\n\n{block2}\n\n\n\noutro"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    # Code blocks preserved verbatim
    assert block1 in result.text
    assert block2 in result.text
    # Blanks between blocks collapsed
    assert "\n\n\n" not in result.text.replace(block1, "").replace(block2, "")


def test_nested_backticks(strategy: CollapseWhitespaceStrategy) -> None:
    """Outer fence governs; inner backticks preserved."""
    nested = "````\n```\ninner\n\n\n\n```\n````"
    text = f"before\n\n\n\n{nested}\n\n\n\nafter"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert nested in result.text


def test_all_whitespace(strategy: CollapseWhitespaceStrategy) -> None:
    """Input that is only blank lines returns single newline."""
    text = "\n\n\n\n\n"
    ctx = SmeltContext(text=text, format=Format.TEXT)
    result = strategy.apply(ctx)
    assert result.text == "\n"


def test_no_trailing_whitespace(strategy: CollapseWhitespaceStrategy) -> None:
    """Already clean input returns ctx unchanged (noop)."""
    text = "line1\n\nline2\nline3"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert result is ctx


def test_indented_code_blocks(strategy: CollapseWhitespaceStrategy) -> None:
    """4-space indented code preserves indentation; only trailing spaces stripped."""
    text = "paragraph\n\n    code_line_1  \n    code_line_2\n\nparagraph2"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    # Leading indentation preserved
    assert "    code_line_1" in result.text
    assert "    code_line_2" in result.text
    # Trailing whitespace stripped
    assert "code_line_1  " not in result.text
