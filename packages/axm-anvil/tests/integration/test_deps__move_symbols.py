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


_ORPHAN_CONDITIONAL_SOURCE = (
    "from __future__ import annotations\n"
    "\n"
    "try:\n"
    "    import tomllib\n"
    "except ModuleNotFoundError:\n"
    "    import tomli as tomllib\n"
    "\n\n"
    "def mover() -> int:\n"
    "    return 1\n"
    "\n\n"
    "def stayer() -> str:\n"
    '    return "no import use"\n'
)


def test_conditional_import_fallback_not_stripped_when_orphaned(
    tmp_path: Path,
) -> None:
    """AC3 regression: moving a symbol that does NOT use a conditional import,
    while NO remaining symbol uses it either, must leave the full guard intact.

    The post-move ruff F401 pass previously stripped the ``except`` fallback
    (``import tomli as tomllib``) down to ``pass`` because it was unused,
    silently changing runtime behavior. The fallback must survive verbatim.
    """
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_ORPHAN_CONDITIONAL_SOURCE)
    tgt.write_text("from __future__ import annotations\n")

    move_symbols(src, tgt, ["mover"], workspace_root=tmp_path)

    source_after = src.read_text()
    assert "try:" in source_after
    assert "import tomllib" in source_after
    assert "except ModuleNotFoundError:" in source_after
    # The fallback handler keeps its full import — not collapsed to ``pass``.
    assert "import tomli as tomllib" in source_after
    assert "except ModuleNotFoundError:\n    pass" not in source_after


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
