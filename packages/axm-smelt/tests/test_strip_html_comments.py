from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.strip_html_comments import StripHtmlCommentsStrategy


@pytest.fixture
def strategy() -> StripHtmlCommentsStrategy:
    return StripHtmlCommentsStrategy()


# --- Unit tests ---


def test_strip_single_line_comment(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(text="text <!-- comment --> more", format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert result.text == "text  more"


def test_strip_multiline_comment(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(
        text="before\n<!-- line1\nline2 -->\nafter",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    assert result.text == "before\nafter"


def test_preserve_code_block_comments(strategy: StripHtmlCommentsStrategy) -> None:
    text = "```html\n<!-- keep -->\n```"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert "<!-- keep -->" in result.text


def test_cleanup_blank_lines(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(
        text="before\n<!-- removed -->\n\nafter",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    # Should not have triple blank lines
    assert "\n\n\n" not in result.text
    assert "before" in result.text
    assert "after" in result.text


def test_name_and_category(strategy: StripHtmlCommentsStrategy) -> None:
    assert strategy.name == "strip_html_comments"
    assert strategy.category == "cosmetic"


# --- Functional tests ---


def test_strip_real_markdown(strategy: StripHtmlCommentsStrategy) -> None:
    text = (
        "# My Document\n"
        "\n"
        "Some content here.\n"
        "\n"
        "<!-- Disabled: old feature flag -->\n"
        "\n"
        "More content below.\n"
    )
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert "<!-- Disabled" not in result.text
    assert "# My Document" in result.text
    assert "Some content here." in result.text
    assert "More content below." in result.text


def test_noop_no_comments(strategy: StripHtmlCommentsStrategy) -> None:
    text = "# Title\n\nJust plain markdown without any HTML comments.\n"
    ctx = SmeltContext(text=text, format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert result is ctx


# --- Edge cases ---


def test_nested_looking_comments(strategy: StripHtmlCommentsStrategy) -> None:
    """Greedy-safe: removes up to first `-->`."""
    ctx = SmeltContext(
        text="<!-- outer <!-- inner --> rest -->",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    assert result.text == " rest -->"


def test_comment_at_start_of_file(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(
        text="<!-- header -->\n# Title",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    assert result.text.lstrip("\n").startswith("# Title")
    assert "<!-- header -->" not in result.text


def test_comment_at_end_of_file(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(
        text="content\n<!-- footer -->",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    assert "<!-- footer -->" not in result.text
    assert result.text.rstrip() == "content"


def test_multiple_comments(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(
        text="a <!-- one --> b <!-- two --> c <!-- three --> d",
        format=Format.MARKDOWN,
    )
    result = strategy.apply(ctx)
    assert "<!--" not in result.text
    assert "a" in result.text
    assert "b" in result.text
    assert "c" in result.text
    assert "d" in result.text


def test_empty_comment(strategy: StripHtmlCommentsStrategy) -> None:
    ctx = SmeltContext(text="before<!----> after", format=Format.MARKDOWN)
    result = strategy.apply(ctx)
    assert "<!--" not in result.text
    assert "before" in result.text
    assert "after" in result.text
