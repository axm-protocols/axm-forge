"""E2E tests for the ``axm-ast impact`` CLI command.

Subprocess black box.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture
def mini_pkg(tmp_path: Path) -> Path:
    """Create a minimal package with a symbol referenced across modules."""
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "core.py").write_text("def helper() -> int:\n    return 1\n")
    (root / "cli.py").write_text(
        "from .core import helper\n\n\ndef main() -> int:\n    return helper()\n"
    )
    return root


def test_cli_impact_compact_prints_markdown(mini_pkg: Path) -> None:
    """``impact --compact`` must render the markdown from ToolResult.text.

    Regression guard for the KeyError('compact') crash: the compact path
    returns ``data={}`` + markdown in ``.text``; the CLI must read ``.text``.
    """
    proc = subprocess.run(
        [
            "axm-ast",
            "impact",
            str(mini_pkg),
            "--symbol",
            "helper",
            "--compact",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "KeyError" not in proc.stderr
    assert "helper" in proc.stdout
    assert proc.stdout.strip()
