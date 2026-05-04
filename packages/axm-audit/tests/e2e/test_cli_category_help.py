from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_help_lists_test_quality() -> None:
    result = subprocess.run(
        ["uv", "run", "axm-audit", "audit", "--help"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "test_quality" in combined
    assert "testing" in combined


def test_cli_invalid_category_lists_valid(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-audit", "audit", str(pkg), "--category", "bogus"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "test_quality" in combined
