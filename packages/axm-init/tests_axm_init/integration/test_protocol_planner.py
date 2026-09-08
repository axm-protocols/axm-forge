from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from axm_init.core.protocol_metadata import merge_protocol_metadata
from axm_init.models.protocol_scaffold import (
    ContractDecl,
    NodeDecl,
    PhaseDecl,
    PromptDecl,
    ProtocolScaffoldDecl,
)


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.mark.integration
def test_computes_plan_without_writing_project_state(tmp_path: Path) -> None:
    """AC7: planning a real captured project tree performs no filesystem writes."""
    declaration = ProtocolScaffoldDecl(
        domain="research",
        unit="paper_note",
        action="exec",
        contracts=[ContractDecl(name="request")],
        nodes=[
            NodeDecl(
                name="draft",
                contract="request",
                prompt="instructions",
            )
        ],
        prompts=[PromptDecl(name="instructions", text="Draft the note.")],
        phases=[PhaseDecl(name="write", nodes=["draft"])],
    )
    metadata = merge_protocol_metadata("# retained\n", declaration)
    metadata_path = tmp_path / "pyproject.toml"
    metadata_path.write_text(metadata)
    occupied = (
        tmp_path
        / "src"
        / "protocols_research"
        / "paper_note"
        / "exec"
        / "nodes"
        / "draft.py"
    )
    occupied.parent.mkdir(parents=True)
    occupied.write_text("def build_draft():\n    return object()\n")

    before = _snapshot(tmp_path)
    inventory = {
        relative_path: payload.decode()
        for relative_path, payload in before.items()
        if relative_path != "pyproject.toml"
    }

    planner: Any = importlib.import_module("axm_init.core.protocol_planner")
    plan = planner.plan_protocol_scaffold(
        declaration=declaration,
        metadata=metadata_path.read_text(),
        inventory=inventory,
    )

    assert plan.operations
    assert plan.metadata
    assert _snapshot(tmp_path) == before
