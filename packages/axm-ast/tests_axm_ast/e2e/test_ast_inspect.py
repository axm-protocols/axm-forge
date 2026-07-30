"""E2E test for ``axm-ast inspect`` surfacing the parser-derived kind.

Subprocess black box (L4 06a5ca28-fb63): the CLI ``--json`` payload for a
genuinely abstract method must carry ``kind == "abstract"``, proving the fix
reaches the shipped binary, not just the in-process tool.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "abstract_following.py"


@pytest.fixture
def abstract_pkg(tmp_path: Path) -> Path:
    """Copy the real abstract-following fixture into an isolated package."""
    pkg_dir = tmp_path / "abstract_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "abstract_following.py").write_text(
        _FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return pkg_dir


def test_ast_inspect_cli_surfaces_abstract_kind(abstract_pkg: Path) -> None:
    """AC1: ``axm-ast inspect --json`` reports ``abstract`` for the ABC method."""
    proc = subprocess.run(
        [
            "axm-ast",
            "inspect",
            str(abstract_pkg),
            "--symbol",
            "AbstractProcessor.process",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "abstract", proc.stdout
