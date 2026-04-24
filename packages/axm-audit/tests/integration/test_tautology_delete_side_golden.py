from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.tautology import TautologyRule

pytestmark = pytest.mark.integration


AXM_WORKSPACES = Path("/Users/gabriel/Documents/Code/python/axm-workspaces")
GOLDEN_SNAPSHOT = (
    Path(__file__).parent / "fixtures" / "tautology_delete_side_golden.json"
)


def _iter_axm_packages() -> list[Path]:
    pkgs: list[Path] = []
    if not AXM_WORKSPACES.exists():
        pytest.skip(f"axm-workspaces not found at {AXM_WORKSPACES}")
    for workspace in AXM_WORKSPACES.iterdir():
        if not workspace.is_dir():
            continue
        pkg_dir = workspace / "packages"
        if pkg_dir.exists():
            pkgs.extend(p for p in pkg_dir.iterdir() if p.is_dir())
        else:
            pkgs.extend(p for p in workspace.iterdir() if p.is_dir())
    return pkgs


def test_axm_all_17_deletes_match_prototype() -> None:
    if not GOLDEN_SNAPSHOT.exists():
        pytest.skip(f"golden snapshot missing at {GOLDEN_SNAPSHOT}")
    golden = json.loads(GOLDEN_SNAPSHOT.read_text())
    golden_set = {
        (entry["pkg"], entry["file"], entry["test"], entry["rule"]) for entry in golden
    }
    assert len(golden_set) == 17, (
        f"golden snapshot must pin exactly 17 DELETE verdicts, got {len(golden_set)}"
    )

    rule = TautologyRule()
    observed: set[tuple[str, str, str, str]] = set()
    for pkg in _iter_axm_packages():
        result = rule.check(pkg)
        verdicts = result.metadata.get("verdicts", [])
        for v in verdicts:
            if v.get("verdict") == "DELETE":
                observed.add((pkg.name, v["file"], v["test"], v["rule"]))

    assert observed == golden_set, (
        f"DELETE verdict set drifted from golden.\n"
        f"  missing: {golden_set - observed}\n"
        f"  extra:   {observed - golden_set}"
    )
