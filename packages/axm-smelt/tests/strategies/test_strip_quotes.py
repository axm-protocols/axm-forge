from __future__ import annotations

import pytest

from axm_smelt.core.models import SmeltContext
from axm_smelt.strategies.strip_quotes import StripQuotesStrategy


@pytest.fixture
def strategy() -> StripQuotesStrategy:
    return StripQuotesStrategy()


class TestStripQuotesBasic:
    def test_strip_quotes_basic(self, strategy: StripQuotesStrategy) -> None:
        result = strategy.apply(SmeltContext(text='{"name":"Alice","age":30}')).text
        assert result == '{name:"Alice",age:30}'

    def test_strip_quotes_special_keys(self, strategy: StripQuotesStrategy) -> None:
        inp = '{"my key":"val","my-key":"val2"}'
        result = strategy.apply(SmeltContext(text=inp)).text
        # Keys with spaces and dashes should keep quotes
        assert '"my key":' in result
        assert '"my-key":' in result

    def test_strip_quotes_nested(self, strategy: StripQuotesStrategy) -> None:
        text = '{"outer":{"inner":"value"}}'
        result = strategy.apply(SmeltContext(text=text)).text
        assert result == '{outer:{inner:"value"}}'


class TestStripQuotesEdgeCases:
    def test_unicode_keys(self, strategy: StripQuotesStrategy) -> None:
        inp = '{"caf\u00e9":"latte","name":"test"}'
        result = strategy.apply(SmeltContext(text=inp)).text
        # Unicode key should preserve quotes (not simple alphanumeric)
        assert '"caf\u00e9":' in result or '"caf\xe9":' in result
        # Simple ASCII key should be unquoted
        assert 'name:"test"' in result
