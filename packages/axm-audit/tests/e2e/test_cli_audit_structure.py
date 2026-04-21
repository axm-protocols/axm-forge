from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.structure import TestsPyramidRule

__all__ = []

pytestmark = pytest.mark.e2e


PYPROJECT = textwrap.dedent(
    """
    [project]
    name = "pkg"
    version = "0.1.0"

    [project.scripts]
    pkg = "pkg.cli:main"

    [tool.pytest.ini_options]
    markers = [
        "integration: integration tests",
        "e2e: end-to-end tests",
    ]
    """
).strip()


def test_cli_audit_structure_shows_pyramid(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    for d in ("tests/unit", "tests/integration", "tests/e2e"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")

    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "axm-audit",
            "audit",
            str(tmp_path),
            "--category",
            "structure",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), proc.stderr
    payload = json.loads(proc.stdout)
    checks = payload.get("checks", [])
    pyramid_rule_id = TestsPyramidRule().rule_id
    assert any(c.get("rule_id") == pyramid_rule_id for c in checks)
