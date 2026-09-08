from __future__ import annotations

import copy
import importlib
from pathlib import PurePosixPath
from types import ModuleType
from typing import Any

import pytest

from axm_init.core.protocol_metadata import merge_protocol_metadata
from axm_init.models.protocol_scaffold import (
    ContractDecl,
    NodeDecl,
    PhaseDecl,
    PromptDecl,
    ProtocolScaffoldDecl,
    TicketDecl,
)

SKELETON_MARKER = "# axm-init: incomplete-skeleton"


@pytest.fixture
def declaration() -> ProtocolScaffoldDecl:
    return ProtocolScaffoldDecl(
        domain="dev",
        unit="work",
        action="exec",
        contracts=[
            ContractDecl(name="request"),
            ContractDecl(name="result"),
        ],
        nodes=[
            NodeDecl(
                name="prepare",
                contract="request",
                prompt="instructions",
            ),
            NodeDecl(name="finish", contract="result"),
        ],
        prompts=[
            PromptDecl(name="instructions", text="Perform only the declared work."),
            PromptDecl(name="review", text="Review the declared result."),
        ],
        phases=[
            PhaseDecl(name="build", nodes=["prepare"]),
            PhaseDecl(name="close", nodes=["finish"]),
        ],
        ticket=TicketDecl(
            ticket_type="dev.work",
            input_contract="request",
        ),
    )


def _planner() -> ModuleType:
    return importlib.import_module("axm_init.core.protocol_planner")


def _plan(
    declaration: ProtocolScaffoldDecl,
    *,
    metadata: str = "",
    inventory: dict[str, str] | None = None,
) -> Any:
    return _planner().plan_protocol_scaffold(
        declaration=declaration,
        metadata=metadata,
        inventory={} if inventory is None else inventory,
    )


def _path(operation: Any) -> str:
    return str(operation.path)


def _status(operation: Any) -> str:
    value = operation.status
    return value.value if hasattr(value, "value") else str(value)


def _operation_map(plan: Any) -> dict[str, Any]:
    return {_path(operation): operation for operation in plan.operations}


def _expected_paths(*, ticket: bool = True) -> list[str]:
    paths = [
        "src/protocols_dev/__init__.py",
        "src/protocols_dev/work/__init__.py",
        "src/protocols_dev/work/exec/__init__.py",
        "src/protocols_dev/work/exec/contracts/__init__.py",
        "src/protocols_dev/work/exec/contracts/request.py",
        "src/protocols_dev/work/exec/contracts/result.py",
        "src/protocols_dev/work/exec/nodes/__init__.py",
        "src/protocols_dev/work/exec/nodes/finish.py",
        "src/protocols_dev/work/exec/nodes/prepare.py",
        "src/protocols_dev/work/exec/phases/__init__.py",
        "src/protocols_dev/work/exec/phases/build.py",
        "src/protocols_dev/work/exec/phases/close.py",
        "src/protocols_dev/work/exec/prompts/__init__.py",
        "src/protocols_dev/work/exec/prompts/instructions.md",
        "src/protocols_dev/work/exec/prompts/review.md",
        "src/protocols_dev/work/exec/protocol.py",
    ]
    if ticket:
        paths.append("src/protocols_dev/work/exec/ticket.py")
    return sorted(paths)


def test_emits_exact_declaration_derived_topology(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC1: emit only the exact declaration-derived protocol topology."""
    plan = _plan(declaration)
    paths = [_path(operation) for operation in plan.operations]

    assert paths == _expected_paths()
    assert all(_status(operation) == "create" for operation in plan.operations)
    assert "src/protocols_dev/work/exec/contracts.py" not in paths
    assert "src/protocols_dev/work/exec/actions.py" not in paths
    assert "src/protocols_dev/work/exec/nodes.py" not in paths

    without_ticket = _plan(declaration.model_copy(update={"ticket": None}))
    assert [_path(operation) for operation in without_ticket.operations] == (
        _expected_paths(ticket=False)
    )


def test_recognizes_implemented_components_without_resetting(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC2: preserve compatible implemented files and create the complement."""
    metadata = merge_protocol_metadata("", declaration)
    implemented = {
        "src/protocols_dev/work/exec/contracts/request.py": (
            "class Request:\n    business_metric: int\n"
        ),
        "src/protocols_dev/work/exec/nodes/prepare.py": (
            "def build_prepare():\n    return object()\n"
        ),
    }

    plan = _plan(declaration, metadata=metadata, inventory=implemented)
    operations = _operation_map(plan)

    assert {
        path
        for path, operation in operations.items()
        if _status(operation) == "unchanged"
    } == set(implemented)
    assert all(operations[path].content is None for path in implemented)
    assert {
        path for path, operation in operations.items() if _status(operation) == "create"
    } == set(_expected_paths()) - set(implemented)
    assert not {
        path
        for path, operation in operations.items()
        if _status(operation) in {"update", "conflict"}
    }


def test_reports_incompatible_occupied_path_as_conflict(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC3: report an occupied path without profile ownership as a conflict."""
    occupied_path = "src/protocols_dev/work/exec/contracts/request.py"

    plan = _plan(
        declaration,
        inventory={occupied_path: "class ForeignOwner:\n    pass\n"},
    )
    operation = _operation_map(plan)[occupied_path]

    assert _status(operation) == "conflict"
    assert operation.content is None
    assert sum(_path(candidate) == occupied_path for candidate in plan.operations) == 1


def test_renders_inert_and_detectable_protocol_skeletons(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC4: render marked, inert skeletons and draft-only metadata."""
    plan = _plan(declaration)
    operations = _operation_map(plan)

    for component in ("prepare", "finish"):
        content = operations[
            f"src/protocols_dev/work/exec/nodes/{component}.py"
        ].content
        assert f'__all__ = ["build_{component}"]' in content
        assert (
            'raise NotImplementedError("Scaffold: implementation required")' in content
        )

    for component in ("build", "close"):
        content = operations[
            f"src/protocols_dev/work/exec/phases/{component}.py"
        ].content
        assert f'__all__ = ["build_{component}"]' in content
        assert (
            'raise NotImplementedError("Scaffold: implementation required")' in content
        )

    for component in ("request", "result"):
        content = operations[
            f"src/protocols_dev/work/exec/contracts/{component}.py"
        ].content
        assert SKELETON_MARKER in content
        model_name = component.title()
        assert f'__all__ = ["{model_name}"]' in content
        assert f"class {model_name}(BaseModel):" in content
        assert "Incomplete generated protocol contract." in content

    for component, prompt_text in (
        ("instructions", "Perform only the declared work."),
        ("review", "Review the declared result."),
    ):
        content = operations[
            f"src/protocols_dev/work/exec/prompts/{component}.md"
        ].content
        assert SKELETON_MARKER in content
        assert prompt_text in content

    rendered = "\n".join(operation.content or "" for operation in plan.operations)
    assert 'state = "draft"' in plan.metadata
    assert "business_metric" not in rendered


def test_leaves_in_memory_inputs_unchanged(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC5: return a plan without mutating metadata or inventory inputs."""
    metadata = "# caller-owned preamble\n"
    inventory = {
        PurePosixPath("src/protocols_dev/__init__.py").as_posix(): (
            "# caller-owned package\n"
        )
    }
    metadata_before = metadata
    inventory_before = copy.deepcopy(inventory)

    plan = _plan(declaration, metadata=metadata, inventory=inventory)

    assert plan.operations
    assert plan.metadata != metadata
    assert metadata == metadata_before
    assert inventory == inventory_before


def test_classifies_owned_incomplete_skeleton_as_update(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC6: update an owned incomplete generated skeleton with merged content."""
    target = "src/protocols_dev/work/exec/contracts/request.py"
    metadata = merge_protocol_metadata("", declaration)

    plan = _plan(
        declaration,
        metadata=metadata,
        inventory={target: f"{SKELETON_MARKER}\n"},
    )
    operation = _operation_map(plan)[target]

    assert _status(operation) == "update"
    assert operation.content is not None
    assert SKELETON_MARKER in operation.content
    assert "Request" in operation.content
    assert sum(_path(candidate) == target for candidate in plan.operations) == 1


def test_plans_prompts_as_markdown_resources(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC2: plan prompts as Markdown, never as Python prompt modules."""
    plan = _plan(declaration)
    prompt_paths = [
        _path(operation)
        for operation in plan.operations
        if "/prompts/" in _path(operation)
    ]

    assert "src/protocols_dev/work/exec/prompts/instructions.md" in prompt_paths
    assert "src/protocols_dev/work/exec/prompts/review.md" in prompt_paths
    assert all(
        path.endswith(".md") or path.endswith("/__init__.py") for path in prompt_paths
    )


def test_plans_one_ticket_declaration_per_ticket_bearing_protocol(
    declaration: ProtocolScaffoldDecl,
) -> None:
    """AC3: keep each ticket declaration beside its protocol assembly."""
    review_declaration = declaration.model_copy(update={"action": "review"})
    paths = {
        *(_path(operation) for operation in _plan(declaration).operations),
        *(_path(operation) for operation in _plan(review_declaration).operations),
    }

    assert "src/protocols_dev/work/exec/protocol.py" in paths
    assert "src/protocols_dev/work/exec/ticket.py" in paths
    assert "src/protocols_dev/work/review/protocol.py" in paths
    assert "src/protocols_dev/work/review/ticket.py" in paths
    assert "src/protocols_dev/work/ticket.py" not in paths
