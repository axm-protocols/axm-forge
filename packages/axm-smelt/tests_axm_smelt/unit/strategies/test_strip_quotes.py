from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.strip_quotes import StripQuotesStrategy


@pytest.fixture
def strategy() -> StripQuotesStrategy:
    return StripQuotesStrategy()


def _json_ctx(text: str) -> SmeltContext:
    """Build a JSON-typed context (strip_quotes only runs on JSON)."""
    return SmeltContext(text=text, format=Format.JSON)


class TestStripQuotesBasic:
    def test_strip_quotes_basic(self, strategy: StripQuotesStrategy) -> None:
        result = strategy.apply(_json_ctx('{"name":"Alice","age":30}')).text
        assert result == '{name:"Alice",age:30}'

    def test_strip_quotes_special_keys(self, strategy: StripQuotesStrategy) -> None:
        inp = '{"my key":"val","my-key":"val2"}'
        result = strategy.apply(_json_ctx(inp)).text
        # Keys with spaces and dashes should keep quotes
        assert '"my key":' in result
        assert '"my-key":' in result

    def test_strip_quotes_nested(self, strategy: StripQuotesStrategy) -> None:
        text = '{"outer":{"inner":"value"}}'
        result = strategy.apply(_json_ctx(text)).text
        assert result == '{outer:{inner:"value"}}'


class TestStripQuotesFormatGuard:
    def test_prose_is_left_untouched(self, strategy: StripQuotesStrategy) -> None:
        """Non-JSON prose must not be mutated: the ``"word":`` pattern also
        matches quoted words in text, so a TEXT-format context is a no-op."""
        prose = 'He said "note": something about "key": values in prose.'
        ctx = SmeltContext(text=prose, format=Format.TEXT)
        assert strategy.apply(ctx).text == prose

    def test_markdown_is_left_untouched(self, strategy: StripQuotesStrategy) -> None:
        """Markdown carrying quoted words is returned unchanged."""
        md = 'See the "config": section and the "options": list.'
        ctx = SmeltContext(text=md, format=Format.MARKDOWN)
        assert strategy.apply(ctx).text == md


class TestStripQuotesEdgeCases:
    def test_unicode_keys(self, strategy: StripQuotesStrategy) -> None:
        inp = '{"caf\u00e9":"latte","name":"test"}'
        result = strategy.apply(_json_ctx(inp)).text
        # Unicode key should preserve quotes (not simple alphanumeric)
        assert '"caf\u00e9":' in result or '"caf\xe9":' in result
        # Simple ASCII key should be unquoted
        assert 'name:"test"' in result
