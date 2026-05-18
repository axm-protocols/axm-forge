"""Integration tests: the rule on the axm-audit project itself (AC9, AC10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.no_package_symbol import (
    NoPackageSymbolRule,
)
from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule

pytestmark = pytest.mark.integration


def _project_root() -> Path:
    """Walk up from this test file to find the axm-audit package root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and parent.name == "axm-audit":
            return parent
    raise RuntimeError("axm-audit project root not found")


def test_rule_does_not_double_flag_with_pyramid_level() -> None:
    """AC10: no file is flagged by both rules for overlapping semantics."""
    root = _project_root()
    nps_findings = NoPackageSymbolRule().check(root).details.get("findings", [])
    pyramid_result = PyramidLevelRule().check(root)
    pyramid_files: set[str] = set()
    for entry in pyramid_result.details.get("mismatches", []) or []:
        if not isinstance(entry, dict):
            continue
        for key in ("file", "test_file", "path"):
            value = entry.get(key)
            if value:
                pyramid_files.add(str(value))
                break
    nps_files = {f["test_file"] for f in nps_findings}
    overlap = nps_files & pyramid_files
    assert overlap == set(), f"Same files flagged by both rules: {overlap}"
