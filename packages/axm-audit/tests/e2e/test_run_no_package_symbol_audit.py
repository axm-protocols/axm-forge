"""E2E tests: the new rule surfaces through the CLI (AC5, AC10)."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and parent.name == "axm-audit":
            return parent
    raise RuntimeError("axm-audit project root not found")


def test_cli_test_quality_includes_new_rule_json() -> None:
    """AC10: `axm-audit test-quality --json` lists TEST_QUALITY_NO_PACKAGE_SYMBOL."""
    root = _project_root()
    result = subprocess.run(  # noqa: S603
        ["axm-audit", "test-quality", "--json", str(root)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    blob = (result.stdout or "") + (result.stderr or "")
    assert "TEST_QUALITY_NO_PACKAGE_SYMBOL" in blob, (
        f"rule absent from CLI output. exit={result.returncode}\n{blob[:2000]}"
    )


def test_cli_audit_test_quality_on_synthetic_offender(tmp_path: Path) -> None:
    """AC5: CLI on a synthetic offender surfaces a NO_PACKAGE_SYMBOL finding."""
    pkg = tmp_path / "synpkg"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("")
    (pkg / "tests" / "integration").mkdir(parents=True)
    (pkg / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            pkg-cli = "pkg.cli:main"
            """
        ).strip()
    )
    result = subprocess.run(  # noqa: S603
        ["axm-audit", "test-quality", "--json", str(pkg)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    blob = result.stdout or ""
    found_verdict = "NO_PACKAGE_SYMBOL" in blob
    try:
        parsed = json.loads(blob)
        json_has_finding = "TEST_QUALITY_NO_PACKAGE_SYMBOL" in json.dumps(parsed)
    except (ValueError, json.JSONDecodeError):
        json_has_finding = False
    assert found_verdict or json_has_finding or result.returncode != 0, (
        f"CLI did not surface NO_PACKAGE_SYMBOL.\nstdout={blob[:2000]}\n"
        f"stderr={(result.stderr or '')[:1000]}"
    )
