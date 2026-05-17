"""Integration tests for the collapse_whitespace strategy (real I/O)."""

from __future__ import annotations

import pytest

from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.collapse_whitespace import CollapseWhitespaceStrategy


@pytest.fixture
def strategy() -> CollapseWhitespaceStrategy:
    return CollapseWhitespaceStrategy()


class TestCollapseWhitespaceIntegration:
    """Integration tests for CollapseWhitespaceStrategy (real I/O)."""

    def test_multiple_code_blocks(self, strategy: CollapseWhitespaceStrategy) -> None:
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
