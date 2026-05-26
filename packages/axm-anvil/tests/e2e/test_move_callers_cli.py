"""E2E tests for `axm-anvil move` CLI caller rewriting."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_move_rewrites_caller(tmp_path: Path) -> None:
    """AC1, AC2: `axm-anvil move` rewrites the caller on disk via the CLI."""
    root = tmp_path
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    old = pkg / "old.py"
    old.write_text("def Foo():\n    return 1\n")
    new = pkg / "new.py"
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo\n\nFoo()\n")

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(old),
            str(new),
            "Foo",
            "--path",
            str(root),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "from pkg.new import Foo" in caller.read_text()
    assert "callers updated" in result.stdout.lower()
