"""E2E tests: ``axm-init scaffold`` then ``axm-init check`` via subprocess."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_scaffold_then_check(tmp_path: Path) -> None:
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
    assert check.returncode in (0, 1), check.stderr
    report = json.loads(check.stdout)

    if "failed" in report:
        failed_names = {f["name"] for f in report["failed"]}
        assert "structure.tests_dir" not in failed_names, report["failed"]
    elif "checks" in report:
        checks = {c["name"]: c for c in report["checks"]}
        assert checks["structure.tests_dir"]["passed"] is True
    else:
        msg = f"Unexpected check report shape: {report}"
        raise AssertionError(msg)
