"""E2E test: ``axm-init check`` surfaces wheel-doc-shipping failures (AXM-1715)."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_check_command_exits_nonzero_on_orphan_doc(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"

            [tool.axm-init.wheel-doc]
            files = ["docs/x.md"]

            [tool.hatch.build.targets.wheel]
            packages = ["src/pkg"]
            """
        ).lstrip()
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_text("# x\n")

    proc = subprocess.run(
        ["uv", "run", "axm-init", "check", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "pyproject.wheel_doc_shipping" in combined
    assert "x.md" in combined
