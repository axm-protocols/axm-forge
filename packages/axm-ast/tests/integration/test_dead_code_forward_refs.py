"""Integration tests for forward-ref aware dead-code detection.

Covers AC5 (axm-ast's own ``_DescribeData`` no longer falsely flagged) and
AC6 (no regression on neighboring workspace packages).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.dead_code import find_dead_code

pytestmark = pytest.mark.integration


_AXM_AST_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACES_ROOT = _AXM_AST_ROOT.parents[2]
_BASELINES_DIR = _AXM_AST_ROOT / "tests" / "fixtures" / "dead_code_baselines"

_NEIGHBORS: dict[str, Path] = {
    "axm-audit": _WORKSPACES_ROOT / "axm-forge" / "packages" / "axm-audit",
    "axm-engine": _WORKSPACES_ROOT / "axm-nexus" / "packages" / "axm-engine",
}


def test_describe_data_not_reported_dead() -> None:
    """After the patch, axm-ast's _DescribeData is no longer flagged."""
    pkg = analyze_package(_AXM_AST_ROOT)
    dead = find_dead_code(pkg)
    assert "_DescribeData" not in {d.name for d in dead}


@pytest.mark.parametrize("pkg_name", sorted(_NEIGHBORS))
def test_workspace_packages_no_regression(pkg_name: str) -> None:
    """Patch must not introduce new dead-code false positives on neighbors.

    Compares post-patch findings against the committed pre-patch baseline.
    The count must be ≤ baseline (the patch can only remove false positives,
    never add them — forward-ref detection is strictly additive to the
    reference set).
    """
    pkg_path = _NEIGHBORS[pkg_name]
    if not pkg_path.exists():
        pytest.skip(f"neighbor package not on disk: {pkg_path}")

    baseline = json.loads(
        (_BASELINES_DIR / f"{pkg_name}.json").read_text(encoding="utf-8"),
    )
    pkg = analyze_package(pkg_path)
    dead = find_dead_code(pkg)

    assert len(dead) <= baseline["count"], (
        f"new dead-code findings on {pkg_name}: "
        f"got {sorted({d.name for d in dead})}, baseline {baseline['names']}"
    )
