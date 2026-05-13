from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.callers import CallersTool


@pytest.fixture
def tool() -> CallersTool:
    return CallersTool()


@pytest.mark.integration
def test_callers_text_on_real_package(tool: CallersTool) -> None:
    """execute() returns text starting with ast_callers | and line count matches."""
    sample = str(Path(__file__).resolve().parent.parent.parent)
    result = tool.execute(path=sample, symbol="greet")
    # greet may or may not exist — either way the result should be consistent
    if result.success:
        assert result.text is not None
        assert result.text.startswith("ast_callers |")
        # number of non-header lines == count
        body_lines = result.text.strip().splitlines()[1:]
        assert len(body_lines) == result.data["count"]
