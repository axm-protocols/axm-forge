from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

from axm_anvil.core.plan import MovePlan
from axm_anvil.tools.move import MoveTool


def _plan(
    moved: Sequence[str] = ("Foo",),
    imports: Sequence[str] = (),
    constants: Sequence[str] = (),
    warnings: Sequence[str] = (),
) -> MovePlan:
    return MovePlan(
        source_text_new="# new source\n",
        target_text_new="# new target\n",
        moved_names=list(moved),
        imports_added=list(imports),
        constants_added=list(constants),
        warnings=list(warnings),
    )


def test_move_tool_name_and_hint():
    tool = MoveTool()
    assert tool.name == "ast_move"
    assert tool.agent_hint
    assert len(tool.agent_hint) <= 200


def test_format_text_compact():
    plan = _plan(
        moved=("Alpha", "Beta"),
        imports=("os", "sys", "pathlib.Path"),
        warnings=("ruff: unused import removed",),
    )
    tool = MoveTool()
    text = tool._format_text(
        plan,
        from_file="src.py",
        to_file="tgt.py",
    )

    assert "ast_move" in text
    assert "2 symbols" in text
    assert "Moved:" in text
    assert "Dependencies:" in text
    assert len(text.splitlines()) <= 25


def test_mcp_entry_point_discoverable():
    code = (
        "from importlib.metadata import entry_points;"
        "eps = entry_points(group='axm.tools');"
        "match = [(e.name, e.value) for e in eps if e.name == 'ast_move'];"
        "print(match)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ast_move" in result.stdout
    assert "axm_anvil.tools.move:MoveTool" in result.stdout
