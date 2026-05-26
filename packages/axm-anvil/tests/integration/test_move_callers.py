"""Integration tests for caller rewriting in :func:`move_symbols`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_anvil.core.move import MoveValidationError, move_symbols
from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal `src/pkg/` workspace with an empty package."""
    root = tmp_path
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    return root


def _write_old_foo(root: Path) -> Path:
    old = root / "src" / "pkg" / "old.py"
    old.write_text("def Foo():\n    return 1\n")
    return old


def _write_empty_new(root: Path) -> Path:
    new = root / "src" / "pkg" / "new.py"
    new.write_text("")
    return new


def test_move_rewrites_three_callers(workspace: Path) -> None:
    """AC1, AC2, AC5: three callers each get `pkg.old` -> `pkg.new` rewrite."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    for i in range(1, 4):
        (pkg / f"caller{i}.py").write_text(
            f"from pkg.old import Foo\n\ndef run{i}():\n    return Foo()\n"
        )

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    for i in range(1, 4):
        text = (pkg / f"caller{i}.py").read_text()
        assert "from pkg.new import Foo" in text
        assert "pkg.old" not in text
    assert "def Foo" not in old.read_text()
    assert len(plan.callers_updated) == 3


def test_move_rewrites_caller_preserves_alias(workspace: Path) -> None:
    """AC3: alias `Foo as F` survives the rewrite; usage `F()` is untouched."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo as F\n\nF()\n")

    move_symbols(old, new, ["Foo"], workspace_root=workspace)

    text = caller.read_text()
    assert "from pkg.new import Foo as F" in text
    assert "F()" in text
    assert "pkg.old" not in text


def test_move_rewrites_partial_import_line(workspace: Path) -> None:
    """AC4: only the moved name is removed from a multi-name import line."""
    pkg = workspace / "src" / "pkg"
    old = pkg / "old.py"
    old.write_text("A = 1\ndef Foo():\n    return 1\nB = 2\n")
    new = _write_empty_new(workspace)
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import A, Foo, B\n\nFoo()\n")

    move_symbols(old, new, ["Foo"], workspace_root=workspace)

    text = caller.read_text()
    assert "from pkg.new import Foo" in text
    assert "from pkg.old import A, B" in text or "from pkg.old import B, A" in text
    assert "from pkg.old import A, Foo, B" not in text


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


def test_move_dry_run_populates_callers_without_writing(workspace: Path) -> None:
    """AC9: dry_run returns `callers_updated` but leaves disk untouched."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "caller1.py").write_text("from pkg.old import Foo\n\nFoo()\n")
    (pkg / "caller2.py").write_text("from pkg.old import Foo\n\nFoo()\n")

    original_old = old.read_text()
    original_new = new.read_text()
    original_c1 = (pkg / "caller1.py").read_text()
    original_c2 = (pkg / "caller2.py").read_text()

    plan = move_symbols(old, new, ["Foo"], dry_run=True, workspace_root=workspace)

    assert len(plan.callers_updated) == 2
    assert old.read_text() == original_old
    assert new.read_text() == original_new
    assert (pkg / "caller1.py").read_text() == original_c1
    assert (pkg / "caller2.py").read_text() == original_c2


def test_move_skips_caller_importing_from_unrelated_module(
    workspace: Path,
) -> None:
    """AC8: caller importing the name from another module is not rewritten."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "unrelated.py").write_text("def Foo():\n    return 'unrelated'\n")
    caller = pkg / "caller.py"
    caller_text = "from pkg.unrelated import Foo\n\nFoo()\n"
    caller.write_text(caller_text)

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    assert caller.read_text() == caller_text
    assert plan.callers_updated == []


def test_move_tool_exposes_callers_updated(workspace: Path) -> None:
    """AC7: MoveTool.execute surfaces `data['callers_updated']` entries."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "caller.py").write_text("from pkg.old import Foo\n\nFoo()\n")

    tool = MoveTool()
    result = tool.execute(
        path=str(workspace),
        symbols="Foo",
        from_file=str(old),
        to_file=str(new),
    )

    assert result.success is True, getattr(result, "error", None)
    callers = result.data["callers_updated"]
    assert isinstance(callers, list)
    assert len(callers) == 1
    entry = callers[0]
    assert set(entry.keys()) == {"file", "line", "old", "new"}
