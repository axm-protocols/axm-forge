"""Integration test: scaffold ↔ init_check agree on the pyramid layout.

The static shape of the templates (directories, markers, starter files) is
covered by unit tests in tests/unit/templates/test_pyramid_layout.py — those
read the template files directly. This module keeps only the closed-loop
check: a freshly scaffolded project must satisfy the `structure.tests_dir`
audit rule, so the two components can't drift silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.tools.check import InitCheckTool
from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.integration


def test_scaffold_then_check_passes_structure_tests_dir(tmp_path: Path) -> None:
    project = tmp_path / "demo-pkg"
    project.mkdir()
    result = InitScaffoldTool().execute(
        path=str(project),
        name=project.name,
        org="DemoOrg",
        author="Demo Author",
        email="demo@example.com",
        license="MIT",
        description="demo package",
    )
    assert result.success, result.error

    check = InitCheckTool().execute(path=str(project))
    assert check.success, check.error

    failed_names = {f["name"] for f in check.data["failed"]}
    assert "structure.tests_dir" not in failed_names, (
        f"structure.tests_dir failed: {check.data['failed']}"
    )
