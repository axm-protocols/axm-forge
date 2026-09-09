"""RED tests for structured protocol scaffold result projection."""

from __future__ import annotations

import importlib
from pathlib import PurePosixPath

from axm_init.core.protocol_planner import (
    PlanOperation,
    PlanStatus,
    ProtocolScaffoldPlan,
)
from axm_init.models.results import ScaffoldResult


def test_project_plan_preserves_typed_protocol_preview_fields() -> None:
    """AC2: project every typed plan status without parsing rendered text."""
    plan = ProtocolScaffoldPlan(
        operations=(
            PlanOperation(PurePosixPath("new.py"), PlanStatus.CREATE, "new"),
            PlanOperation(PurePosixPath("changed.py"), PlanStatus.UPDATE, "changed"),
            PlanOperation(PurePosixPath("same.py"), PlanStatus.UNCHANGED, None),
            PlanOperation(PurePosixPath("blocked.py"), PlanStatus.CONFLICT, None),
        ),
        metadata='[project]\nname = "protocols-dev"\n',
    )

    protocol_scaffolder = importlib.import_module("axm_init.core.protocol_scaffolder")
    result = protocol_scaffolder.build_protocol_scaffold_result(
        plan,
        profile="protocols",
        mode="member",
        root=PurePosixPath("packages/protocols-dev"),
        graph_names=("dev.work.create",),
        preview=True,
    )

    assert isinstance(result, ScaffoldResult)
    assert result.profile == "protocols"
    assert result.mode == "member"
    assert result.root == "packages/protocols-dev"
    assert result.preview is True
    assert result.created == ["new.py"]
    assert result.updated == ["changed.py"]
    assert result.unchanged == ["same.py"]
    assert result.conflicts == ["blocked.py"]
    assert result.protocols == ["dev.work.create"]
