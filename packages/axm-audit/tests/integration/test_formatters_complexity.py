from __future__ import annotations

from pathlib import Path

import pytest
from radon.complexity import cc_visit

import axm_audit.formatters as formatters_module

pytestmark = pytest.mark.integration

CC_BUDGET = 10


@pytest.fixture(scope="module")
def cc_blocks() -> dict[str, int]:
    source = Path(formatters_module.__file__).read_text()
    return {block.name: block.complexity for block in cc_visit(source)}


def test_extract_test_quality_cc_within_budget(cc_blocks: dict[str, int]) -> None:
    assert cc_blocks["_extract_test_quality"] <= CC_BUDGET


def test_format_agent_text_cc_within_budget(cc_blocks: dict[str, int]) -> None:
    assert cc_blocks["format_agent_text"] <= CC_BUDGET


def test_new_helpers_within_budget(cc_blocks: dict[str, int]) -> None:
    excessive = {name: cc for name, cc in cc_blocks.items() if cc > CC_BUDGET}
    excessive.pop("format_agent", None)
    assert not excessive, f"Functions exceed CC budget {CC_BUDGET}: {excessive}"
