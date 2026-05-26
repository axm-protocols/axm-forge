from __future__ import annotations

import pytest

from axm_anvil.core.move import move_symbols


def test_move_shared_helpers_extract_raises(tmp_path):
    src = tmp_path / "src.py"
    tgt = tmp_path / "tgt.py"
    src.write_text("def foo():\n    return 1\n")
    tgt.write_text("")
    with pytest.raises(NotImplementedError, match="extract mode arrives in Phase 3"):
        move_symbols(
            src,
            tgt,
            ["foo"],
            shared_helpers="extract",
            dry_run=True,
            workspace_root=tmp_path,
        )


def test_move_shared_helpers_module_raises(tmp_path):
    src = tmp_path / "src.py"
    tgt = tmp_path / "tgt.py"
    src.write_text("def foo():\n    return 1\n")
    tgt.write_text("")
    with pytest.raises(NotImplementedError):
        move_symbols(
            src,
            tgt,
            ["foo"],
            shared_helpers_module="_helpers",
            dry_run=True,
            workspace_root=tmp_path,
        )
