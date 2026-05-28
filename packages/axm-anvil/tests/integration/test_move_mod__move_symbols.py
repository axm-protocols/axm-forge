"""Split from ``test_move_callers.py``."""

from pathlib import Path

from pytest_mock import MockerFixture

from axm_anvil.core.move import move_symbols
from tests.integration._helpers import _write_empty_new, _write_old_foo


def test_move_atomic_batch_includes_callers(
    workspace: Path, mocker: MockerFixture
) -> None:
    """AC5: a single `batch_edit` call carries source + target + all callers."""
    import axm_anvil.core.move as move_mod

    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "caller1.py").write_text("from pkg.old import Foo\n\nFoo()\n")
    (pkg / "caller2.py").write_text("from pkg.old import Foo\n\nFoo()\n")

    spy = mocker.spy(move_mod, "batch_edit")

    move_symbols(old, new, ["Foo"], workspace_root=workspace)

    assert spy.call_count == 1
    _root_arg, ops = spy.call_args.args
    assert isinstance(ops, list)
    assert len(ops) == 4  # source + target + caller1 + caller2
    assert all(op.get("op") == "replace" for op in ops)
