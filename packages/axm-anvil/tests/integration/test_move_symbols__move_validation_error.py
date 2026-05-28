"""Split from ``test_move_callers.py``."""

from pathlib import Path

import pytest

from axm_anvil.core.move import MoveValidationError, move_symbols
from tests.integration._helpers import _write_empty_new, _write_old_foo


def test_move_caller_parse_error_rolls_back(workspace: Path) -> None:
    """AC6: an unparseable rendered caller raises and no file is written."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    caller = pkg / "caller.py"
    # Valid import line but the body is syntactically broken.
    caller.write_text("from pkg.old import Foo\ndef broken(\n")

    original_caller = caller.read_text()
    original_old = old.read_text()
    original_new = new.read_text()

    with pytest.raises(MoveValidationError):
        move_symbols(old, new, ["Foo"], workspace_root=workspace)

    assert caller.read_text() == original_caller
    assert old.read_text() == original_old
    assert new.read_text() == original_new
