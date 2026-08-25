from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _build_fixture_pkg(root: Path) -> Path:
    pkg = root / "sample_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "protocols.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol\n\n"
        "class Handler(Protocol):\n"
        "    def handle(self, x: int) -> str: ...\n"
    )
    (pkg / "impl.py").write_text(
        "from __future__ import annotations\n\n"
        "class ConcreteHandler:\n"
        "    def handle(self, x: int) -> str:\n"
        "        return 'ok'\n"
    )
    return pkg


def test_entry_point_resolves_to_tool_class() -> None:
    """AC1: axm.tools entry point ast_coupling_gaps loads the CouplingGapsTool class."""
    from importlib.metadata import entry_points

    from axm_ast.tools.coupling_gaps import CouplingGapsTool

    eps = entry_points(group="axm.tools")
    names = {ep.name for ep in eps}
    assert "ast_coupling_gaps" in names
    ep = next(ep for ep in eps if ep.name == "ast_coupling_gaps")
    assert ep.load() is CouplingGapsTool


def test_execute_returns_success_with_three_data_keys(tmp_path: Path) -> None:
    """AC2: execute returns ToolResult(success=True) with the three coupling keys."""
    from axm_ast.tools.coupling_gaps import CouplingGapsTool

    pkg = _build_fixture_pkg(tmp_path)
    result = CouplingGapsTool().execute(path=str(pkg), symbols=["Handler"])

    assert result.success is True
    keys = {"reference_coupled", "protocol_coupled", "value_coupled"}
    assert keys.issubset(result.data.keys())


def test_text_carries_caveat_and_counts(tmp_path: Path) -> None:
    """AC3: ToolResult.text carries the lower-bound caveat and the site counts."""
    from axm_ast.tools.coupling_gaps import CouplingGapsTool

    pkg = _build_fixture_pkg(tmp_path)
    result = CouplingGapsTool().execute(path=str(pkg), symbols=["Handler"])

    protocol_count = sum(len(v) for v in result.data["protocol_coupled"].values())
    value_count = sum(len(v) for v in result.data["value_coupled"].values())

    assert "lower-bound" in result.text.lower()
    assert str(protocol_count) in result.text
    assert str(value_count) in result.text


def test_execute_performs_no_writes(tmp_path: Path) -> None:
    """AC5: execute is read-only — the source-tree fingerprint is unchanged."""
    from axm_ast.core.analyzer import fingerprint_source_tree
    from axm_ast.tools.coupling_gaps import CouplingGapsTool

    pkg = _build_fixture_pkg(tmp_path)
    before = fingerprint_source_tree(pkg)
    CouplingGapsTool().execute(path=str(pkg), symbols=["Handler"])
    after = fingerprint_source_tree(pkg)

    assert after == before
