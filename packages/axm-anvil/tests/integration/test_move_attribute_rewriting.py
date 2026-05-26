from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


@pytest.fixture
def pkg_dir(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    return pkg


def test_move_rewrites_module_import_caller(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old\n\npkg.old.Foo()\n")

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "import pkg.old" not in caller
    assert any(str(entry.file).endswith("caller.py") for entry in plan.callers_updated)


def test_move_rewrites_alias_import(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old as om\n\nom.Foo()\n")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "import pkg.old as om" not in caller


def test_move_preserves_old_import_when_still_used(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "def Foo():\n    return 1\n\n\ndef Bar():\n    return 2\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text(
        "import pkg.old\n\npkg.old.Foo()\npkg.old.Bar()\n"
    )

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.old" in caller
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "pkg.old.Bar()" in caller


def test_move_attribute_rewrite_preserves_method_chain(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "class Foo:\n    def validate(self):\n        return True\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old\n\npkg.old.Foo().validate()\n")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "pkg.new.Foo().validate()" in caller


def test_move_mixed_from_and_module_imports_in_same_caller(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "def Foo():\n    return 1\n\n\ndef Bar():\n    return 2\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text(
        "from pkg.old import Bar\nimport pkg.old\n\npkg.old.Foo()\nBar()\n"
    )

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo", "Bar"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "from pkg.new import Bar" in caller
    assert "pkg.new.Foo()" in caller
    assert "from pkg.old import Bar" not in caller
    assert "import pkg.old\n" not in caller
