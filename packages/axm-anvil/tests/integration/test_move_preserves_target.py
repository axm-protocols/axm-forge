from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_preserves_target_existing_symbols(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Moved:\n    pass\n")
    original_target = (
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "EXISTING = 1\n\n"
        "class AlreadyHere:\n    pass\n"
    )
    tgt.write_text(original_target)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["Moved"], dry_run=False)
    target_text = tgt.read_text()
    assert "class AlreadyHere" in target_text
    assert "EXISTING = 1" in target_text
    assert "from pathlib import Path" in target_text
    assert "class Moved" in target_text
