"""Integration: ``move_symbols`` still resolves the workspace module graph.

Guards AC3 of AXM-2136 — repointing anvil's workspace-graph imports onto the
public ``axm_ast`` surface must not regress the move pipeline: a cross-module
move must still resolve callers through the workspace graph and rewrite them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_still_resolves_workspace_graph(workspace: Path) -> None:
    """AC3: a cross-module move updates callers via the workspace graph."""
    pkg = workspace / "src" / "pkg"
    old = pkg / "old.py"
    new = pkg / "new.py"
    old.write_text("def Foo():\n    return 1\n")
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo\n\nFoo()\n")

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    # The workspace graph was resolved: the caller import was rewritten to the
    # new module (proof the move pipeline still walks the workspace module
    # graph through the public axm_ast surface).
    assert "Foo" in plan.moved_names
    caller_text = caller.read_text()
    assert "from pkg.new import Foo" in caller_text
    assert "from pkg.old import Foo" not in caller_text
