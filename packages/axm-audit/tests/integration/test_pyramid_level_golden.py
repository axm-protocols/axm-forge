"""Byte-parity integration tests: PyramidLevelRule vs reference prototype.

Spec: AXM-1502 AC9/AC10 — the real rule must produce an output set identical
to the reference prototype script across representative AXM packages.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule

pytestmark = pytest.mark.integration

_WORKSPACES = Path("/Users/gabriel/Documents/Code/python/axm-workspaces")
_PROTOTYPE_CANDIDATES = (
    _WORKSPACES / "axm-forge/packages/axm-audit/scripts/detect_pyramid_level_v6.py",
    _WORKSPACES / "axm-forge/packages/axm-audit/tools/detect_pyramid_level_v6.py",
    Path(__file__).resolve().parents[2] / "scripts" / "detect_pyramid_level_v6.py",
    Path(__file__).resolve().parents[2] / "tools" / "detect_pyramid_level_v6.py",
)


def _prototype_path() -> Path:
    for candidate in _PROTOTYPE_CANDIDATES:
        if candidate.exists():
            return candidate
    pytest.skip(
        "detect_pyramid_level_v6.py prototype not found; update _PROTOTYPE_CANDIDATES"
    )
    raise RuntimeError  # pragma: no cover — appeases type checker


def _prototype_set(pkg_path: Path) -> set[tuple[str, str, str]]:
    script = _prototype_path()
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "python", str(script), "--json", str(pkg_path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    findings = data if isinstance(data, list) else data.get("findings", [])
    return {
        (
            str(Path(item["path"]).resolve()),
            item["function"],
            item["level"],
        )
        for item in findings
    }


def _rule_set(pkg_path: Path) -> set[tuple[str, str, str]]:
    result = PyramidLevelRule().check(pkg_path)
    return {
        (
            str(Path(f.path).resolve()),
            f.function,
            f.level,
        )
        for f in result.findings
    }


def _require_pkg(pkg_path: Path) -> None:
    if not pkg_path.exists():
        pytest.skip(f"package not present: {pkg_path}")


@pytest.mark.parametrize(
    "pkg_relpath",
    [
        "axm-forge/packages/axm-audit",
        "axm-forge/packages/axm-ast",
        "axm-nexus/packages/axm-engine",
    ],
    ids=["axm-audit", "axm-ast", "axm-engine"],
)
def test_rule_output_matches_prototype(pkg_relpath: str) -> None:
    """AC9/AC10: rule output is byte-identical to the reference prototype."""
    # Across representative packages.
    pkg = _WORKSPACES / pkg_relpath
    _require_pkg(pkg)
    assert _rule_set(pkg) == _prototype_set(pkg)
