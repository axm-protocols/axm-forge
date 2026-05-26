from __future__ import annotations

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


@pytest.fixture
def pkg_dir(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    return pkg


def test_reexport_injects_line_in_source(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    source = (pkg_dir / "old.py").read_text()
    assert "from pkg.new import Foo" in source
    assert "# re-export for backwards compat" in source
    assert "def Foo" not in source


def test_reexport_leaves_callers_untouched(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    caller_text = "from pkg.old import Foo\n\nFoo()\n"
    (pkg_dir / "caller.py").write_text(caller_text)

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    assert (pkg_dir / "caller.py").read_text() == caller_text
    assert plan.callers_updated == []


def test_reexport_dry_run_includes_export_line(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
        dry_run=True,
    )

    assert "from pkg.new import Foo" in plan.source_text_new
    assert "def Foo" in (pkg_dir / "old.py").read_text()


def test_reexport_atomic_single_batch_edit(
    tmp_path: Path, pkg_dir: Path, mocker: MockerFixture
) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    spy = mocker.patch("axm_anvil.core.move.batch_edit")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    assert spy.call_count == 1
    call = spy.call_args
    args = call.args
    ops = args[1] if len(args) > 1 else call.kwargs["operations"]
    replace_ops = [op for op in ops if op["op"] == "replace"]
    assert len(replace_ops) == 2


def test_reexport_with_rename_raises(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    with pytest.raises(ValueError):
        move_symbols(
            pkg_dir / "old.py",
            pkg_dir / "new.py",
            ["Foo"],
            workspace_root=tmp_path,
            reexport=True,
            rename={"Foo": "Bar"},
        )
