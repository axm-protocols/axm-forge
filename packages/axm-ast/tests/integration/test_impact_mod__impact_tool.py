"""Split from ``test_tools_impact.py``."""

from typing import Any

import pytest

from axm_ast.tools.impact import ImpactTool


@pytest.fixture
def impact_tool() -> ImpactTool:
    return ImpactTool()


def test_execute_with_symbols_only_takes_batch_path(
    impact_tool: ImpactTool, mocker: Any, tmp_path: Any
) -> None:
    """AC2: providing only ``symbols`` routes through ``_execute_batch``.

    Spies on the helpers to confirm the batch branch is taken (and not the
    single-symbol branch) when ``symbol is None`` but ``symbols`` is set.
    """
    from axm_ast.tools import impact as impact_mod

    batch_spy = mocker.spy(impact_mod.ImpactTool, "_execute_batch")
    single_spy = mocker.spy(impact_mod.ImpactTool, "_execute_single")

    # Stub the heavy analysis helper so we don't need a real package layout.
    mocker.patch.object(
        impact_mod.ImpactTool,
        "_analyze_single",
        return_value={"symbol": "foo", "error": "stubbed"},
    )

    result = impact_tool.execute(
        path=str(tmp_path),
        symbol=None,
        symbols=["foo", "bar"],
    )

    assert batch_spy.call_count == 1
    assert single_spy.call_count == 0
    # Batch result shape: data carries per-symbol entries under "symbols".
    assert result.success is True
    assert isinstance(result.data, dict)
    assert "symbols" in result.data
    assert len(result.data["symbols"]) == 2
