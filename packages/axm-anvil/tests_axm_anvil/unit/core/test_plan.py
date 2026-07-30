from __future__ import annotations

from axm_anvil.core.plan import MovePlan, SharedHelpersError


def test_move_plan_dataclass_defaults() -> None:
    plan = MovePlan(
        source_text_new="",
        target_text_new="",
        moved_names=[],
    )
    assert plan.warnings == []
    assert plan.imports_added == []
    assert plan.constants_added == []


def test_shared_helpers_error_exception_dataclass():
    exc = SharedHelpersError(shared_helpers=["_h1", "_h2"])
    message = str(exc)
    assert "_h1" in message
    assert "_h2" in message
