"""Integration: the package root re-exports the full public contract.

AC1 — ``move_symbols``, ``rename_symbols`` and ``extract_symbols`` (plus the
tools, plan models and typed exceptions) resolve straight from the
``axm_anvil`` package root and run end-to-end on a temporary workspace.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import axm_anvil
from axm_anvil import (
    ExtractTool,
    MovePlan,
    MoveTool,
    RenamePlan,
    RenameTool,
    SymbolNotFoundError,
    extract_symbols,
    move_symbols,
    rename_symbols,
)

pytestmark = [pytest.mark.integration, pytest.mark.no_package_symbol_ok]


def _mkpkg(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n")
    pkg = root / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "src.py").write_text("def alpha() -> int:\n    return 1\n")
    (pkg / "dst.py").write_text('"""dst."""\n')


def test_package_root_exposes_full_public_contract() -> None:
    """AC1: tools, functions, plans and a typed exception all export cleanly."""
    for name in (
        "MoveTool",
        "RenameTool",
        "ExtractTool",
        "move_symbols",
        "rename_symbols",
        "extract_symbols",
        "MovePlan",
        "RenamePlan",
        "SymbolNotFoundError",
    ):
        assert name in axm_anvil.__all__
        assert hasattr(axm_anvil, name)
    assert issubclass(SymbolNotFoundError, Exception)
    assert MoveTool().name == "anvil_move"
    assert RenameTool().name == "anvil_rename"
    assert ExtractTool().name == "anvil_extract"


def test_public_entrypoints_run_on_tmp_workspace(tmp_path: Path) -> None:
    """AC1: the three functions resolve from the root and run (dry-run)."""
    _mkpkg(tmp_path)
    src = tmp_path / "demo" / "src.py"
    dst = tmp_path / "demo" / "dst.py"

    move_plan = move_symbols(src, dst, ["alpha"], dry_run=True, workspace_root=tmp_path)
    assert isinstance(move_plan, MovePlan)
    assert move_plan.moved_names == ["alpha"]

    extract_plan = extract_symbols(
        src,
        tmp_path / "demo" / "new.py",
        ["alpha"],
        dry_run=True,
        workspace_root=tmp_path,
    )
    assert isinstance(extract_plan, MovePlan)
    assert extract_plan.moved_names == ["alpha"]

    rename_plan = rename_symbols(
        tmp_path, src, {"alpha": "beta"}, dry_run=True, workspace_root=tmp_path
    )
    assert isinstance(rename_plan, RenamePlan)
    assert rename_plan.renamed == {"alpha": "beta"}
