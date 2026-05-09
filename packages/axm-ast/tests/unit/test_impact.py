from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_ast.core.impact import REEXPORT_WEIGHT, ImpactReport, score_impact


def test_score_impact_returns_high_above_threshold() -> None:
    report = ImpactReport(callers=[{}] * 5)
    assert score_impact(report) == "HIGH"


def test_score_impact_returns_low_below_medium() -> None:
    report = ImpactReport(callers=[{}] * 1)
    assert score_impact(report) == "LOW"


def test_score_impact_reexport_double_weight() -> None:
    one_reexport = ImpactReport(reexports=["some.module"])
    equivalent_callers = ImpactReport(callers=[{}] * REEXPORT_WEIGHT)
    assert score_impact(one_reexport) == score_impact(equivalent_callers)


def test_impact_report_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        ImpactReport(unknown_field=[])  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# AC2: ImpactTool.execute() control-flow restructuring (no production assert)
# ---------------------------------------------------------------------------


from typing import Any  # noqa: E402

from axm_ast.tools.impact import ImpactTool  # noqa: E402


@pytest.fixture
def impact_tool() -> ImpactTool:
    return ImpactTool()


def test_execute_with_neither_symbol_nor_symbols_returns_error(
    impact_tool: ImpactTool, tmp_path: Any
) -> None:
    """AC2: missing both ``symbol`` and ``symbols`` returns a clear error."""
    result = impact_tool.execute(path=str(tmp_path), symbol=None, symbols=None)

    assert result.success is False
    assert result.error is not None
    assert "symbol" in result.error.lower()


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


class TestScoreImpactFromDict:
    """Test impact scoring."""

    def test_high_impact(self) -> None:
        """Many callers + re-exported = HIGH."""
        result = {
            "callers": [1, 2, 3, 4, 5],
            "reexports": ["__init__"],
            "affected_modules": ["a", "b", "c"],
        }
        assert score_impact(result) == "HIGH"

    def test_low_impact(self) -> None:
        """No callers, no re-exports = LOW."""
        result: dict[str, list[str | int]] = {
            "callers": [],
            "reexports": [],
            "affected_modules": [],
        }
        assert score_impact(result) == "LOW"

    def test_medium_impact(self) -> None:
        """Some callers = MEDIUM."""
        result = {
            "callers": [1, 2],
            "reexports": [],
            "affected_modules": ["a"],
        }
        assert score_impact(result) == "MEDIUM"
