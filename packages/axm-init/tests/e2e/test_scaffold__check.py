"""E2E tests: ``axm-init scaffold`` then ``axm-init check`` via subprocess."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_scaffold_then_check_scores_100(tmp_path: Path) -> None:
    """AC3: a fresh scaffold scores exactly 100 and exits 0."""
    project = tmp_path / "demo-pkg"
    project.mkdir()

    scaffold = subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "scaffold",
            str(project),
            "--org",
            "DemoOrg",
            "--author",
            "Demo Author",
            "--email",
            "demo@example.com",
            "--license",
            "MIT",
            "--description",
            "demo package",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert scaffold.returncode == 0, scaffold.stderr

    check = subprocess.run(
        ["uv", "run", "axm-init", "check", str(project), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    # AC3: a fresh scaffold must score exactly 100 and exit 0 — no longer
    # tolerate ``returncode in (0, 1)`` without a score constraint.
    assert check.returncode == 0, check.stderr
    report = json.loads(check.stdout)
    assert report["score"] == 100, report.get("failures", report)
