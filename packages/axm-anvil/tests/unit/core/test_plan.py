from __future__ import annotations

from axm_anvil.core.plan import MovePlan


def test_move_plan_dataclass_defaults() -> None:
    plan = MovePlan(
        source_text_new="",
        target_text_new="",
        moved_names=[],
    )
    assert plan.warnings == []
    assert plan.imports_added == []
    assert plan.constants_added == []
