from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_cli_move_no_f811_with_overlapping_target_imports(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pkg.models import ClassInfo\n\n"
        "class Foo:\n"
        "    def run(self) -> ClassInfo:\n"
        "        return ClassInfo()\n"
    )
    tgt.write_text(
        "from __future__ import annotations\nfrom pkg.models.nodes import ClassInfo\n"
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\nversion='0.0.0'\n")

    move_result = subprocess.run(
        ["uv", "run", "axm-anvil", "move", str(src), str(tgt), "Foo"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert move_result.returncode == 0, move_result.stderr
    # AC4: no ruff fallback warning surfaced through CLI output.
    assert "ruff check exited" not in move_result.stdout
    assert "ruff check exited" not in move_result.stderr

    # Independently verify the rewritten target file has no F811.
    ruff_result = subprocess.run(
        ["uv", "run", "ruff", "check", str(tgt)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert ruff_result.returncode == 0, ruff_result.stdout + ruff_result.stderr
