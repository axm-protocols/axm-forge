"""Rename-collision integration test (P1-1).

Renaming a symbol onto a name already defined in the same module would write
two definitions of that name (the second silently shadows the first at import).
``rename_symbols`` must refuse the collision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.plan import SymbolAlreadyExistsError
from axm_anvil.core.rename import rename_symbols

pytestmark = pytest.mark.integration


def test_rename_onto_existing_name_raises_collision(tmp_path: Path) -> None:
    """Renaming ``foo`` to an already-defined ``bar`` refuses the collision
    instead of writing two ``def bar`` in the same module."""
    mod = tmp_path / "mod.py"
    original = "def foo() -> int:\n    return 1\n\n\ndef bar() -> int:\n    return 2\n"
    mod.write_text(original)

    with pytest.raises(SymbolAlreadyExistsError):
        rename_symbols(tmp_path, "mod.py", {"foo": "bar"}, workspace_root=tmp_path)

    # The colliding rename is rejected before any write: file unchanged.
    assert mod.read_text() == original
