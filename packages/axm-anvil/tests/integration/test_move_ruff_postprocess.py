from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_ruff_postprocess_runs(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "class Moves:\n"
        "    def run(self) -> Path:\n"
        "        return Path('x')\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["Moves"], dry_run=False)
    source_text = src.read_text()
    assert "from pathlib import Path" not in source_text


def test_move_ruff_failure_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Foo:\n    pass\n")
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    import subprocess

    original_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and isinstance(cmd, list) and cmd[0] == "ruff":
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="ruff boom"
            )
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(
        "axm_anvil.core.postprocess.subprocess.run", fake_run, raising=False
    )

    plan = move_symbols(src, tgt, ["Foo"], dry_run=False)
    assert plan.warnings
    assert any("ruff" in w.lower() for w in plan.warnings)
