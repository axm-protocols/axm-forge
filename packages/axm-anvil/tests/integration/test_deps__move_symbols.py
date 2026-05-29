from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


_CONDITIONAL_SOURCE = (
    "try:\n"
    "    import fast_json as json\n"
    "except ImportError:\n"
    "    import json\n"
    "\n\n"
    "def encode(value):\n"
    "    return json.dumps(value)\n"
)


def test_conditional_import_block_copied(tmp_path: Path) -> None:
    """AC2: moving a symbol that uses a conditionally-imported name copies the
    entire try/except guard block into the target, not a flat import."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_CONDITIONAL_SOURCE)
    tgt.write_text("")

    move_symbols(src, tgt, ["encode"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert "try:" in target_after
    assert "import fast_json as json" in target_after
    assert "except ImportError:" in target_after


def test_conditional_import_not_removed_from_source(tmp_path: Path) -> None:
    """AC3: the conditional import is never auto-removed from the source even
    when no remaining source symbol references it."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_CONDITIONAL_SOURCE)
    tgt.write_text("")

    move_symbols(src, tgt, ["encode"], workspace_root=tmp_path)

    source_after = src.read_text()
    assert "try:" in source_after
    assert "import fast_json as json" in source_after
    assert "except ImportError:" in source_after


def test_conditional_import_move_real_files(tmp_path: Path) -> None:
    """AC2,AC5: a real on-disk move into a target that already holds an
    equivalent guard block yields exactly one guard block (no duplicate)."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_CONDITIONAL_SOURCE)
    tgt.write_text(
        "try:\n"
        "    import fast_json as json\n"
        "except ImportError:\n"
        "    import json\n"
        "\n\n"
        "def existing():\n"
        '    return json.loads("{}")\n'
    )

    move_symbols(src, tgt, ["encode"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert target_after.count("except ImportError:") == 1
