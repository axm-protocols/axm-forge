from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_move_reexport_flag(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg / "new.py").write_text("")
    caller_text = "from pkg.old import Foo\n\nFoo()\n"
    (pkg / "caller.py").write_text(caller_text)

    result = subprocess.run(
        [
            "uv",
            "run",
            "axm-anvil",
            "move",
            str(pkg / "old.py"),
            str(pkg / "new.py"),
            "Foo",
            "--reexport",
            "--path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    source = (pkg / "old.py").read_text()
    assert "from pkg.new import Foo" in source
    assert "# re-export for backwards compat" in source
    assert (pkg / "caller.py").read_text() == caller_text
