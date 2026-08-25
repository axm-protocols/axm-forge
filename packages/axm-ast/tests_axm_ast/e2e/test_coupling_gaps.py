from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _build_fixture_pkg(root: Path) -> Path:
    pkg = root / "sample_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "protocols.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol\n\n"
        "class Handler(Protocol):\n"
        "    def handle(self, x: int) -> str: ...\n"
    )
    (pkg / "impl.py").write_text(
        "from __future__ import annotations\n\n"
        "class ConcreteHandler:\n"
        "    def handle(self, x: int) -> str:\n"
        "        return 'ok'\n"
    )
    return pkg


def test_cli_prints_report(tmp_path: Path) -> None:
    """AC4: `axm ast_coupling_gaps <pkg>` exits 0 and prints the report."""
    pkg = _build_fixture_pkg(tmp_path)
    proc = subprocess.run(
        ["axm", "ast_coupling_gaps", str(pkg)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "lower-bound" in proc.stdout.lower()
