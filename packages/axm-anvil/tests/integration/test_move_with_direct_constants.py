from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_with_direct_constants(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "FIXTURES = Path('x')\n\n"
        "class Uses:\n"
        "    def run(self) -> Path:\n"
        "        return FIXTURES\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()
    assert "FIXTURES" in target_text
    assert "class Uses" in target_text
    assert "FIXTURES" in plan.constants_added

    source_text = src.read_text()
    assert "class Uses" not in source_text
