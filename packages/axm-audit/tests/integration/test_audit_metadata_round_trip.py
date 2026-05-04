from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_agent

pytestmark = pytest.mark.integration


def _scaffold(root: Path) -> None:
    pkg = root / "src" / "sample_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("def add(a, b):\n    return a + b\n")
    tests = root / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "__init__.py").write_text("")
    (tests / "test_taut.py").write_text("def test_truthy():\n    assert True\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.0.1"\n'
        'requires-python = ">=3.12"\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
        "[tool.hatch.build.targets.wheel]\n"
        'packages = ["src/sample_pkg"]\n'
    )


def test_audit_project_tautology_metadata_round_trip(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    result = audit_project(tmp_path)
    out = format_agent(result)
    taut_entries = [
        e for e in out["failed"] if e["rule_id"] == "TEST_QUALITY_TAUTOLOGY"
    ]
    assert taut_entries, "expected a TEST_QUALITY_TAUTOLOGY failure"
    entry = taut_entries[0]
    assert "metadata" in entry
    verdicts = entry["metadata"]["verdicts"]
    assert verdicts
    first = verdicts[0]
    for key in ("file", "test", "line", "pattern", "verdict", "reason"):
        assert key in first
