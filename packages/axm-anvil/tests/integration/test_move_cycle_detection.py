from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import ImportCycleError
from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


def _write_pyproject(root: Path, name: str = "mypkg") -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
    )


def _setup_cycle_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text(
        "from mypkg.b import helper\n"
        "\n"
        "def Bar():\n"
        "    return 1\n"
        "\n"
        "def uses_helper():\n"
        "    return helper()\n"
        "\n"
        "def Foo():\n"
        "    return Bar()\n"
    )
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return tmp_path, a, b


def test_move_refuses_cycle_introduction(tmp_path: Path) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()
    with pytest.raises(ImportCycleError):
        move_symbols(a, b, ["Foo"], workspace_root=root)
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_move_tool_maps_cycle_error(tmp_path: Path) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
    )
    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Import cycle:")
    assert "mypkg.a" in result.error
    assert "mypkg.b" in result.error


def test_move_allows_preexisting_cycle(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "x.py").write_text("from mypkg.y import Y\n\ndef X():\n    return Y()\n")
    (pkg / "y.py").write_text("from mypkg.x import X\n\ndef Y():\n    return 1\n")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")

    plan = move_symbols(a, b, ["Foo"], workspace_root=tmp_path)
    assert "Foo" in plan.moved_names
    assert "def Foo" in b.read_text()
    assert "def Foo" not in a.read_text()


def test_move_cross_package_skips_cycle_check(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    (tmp_path / "src" / "pkg_a").mkdir(parents=True)
    (tmp_path / "src" / "pkg_b").mkdir(parents=True)
    (tmp_path / "src" / "pkg_a" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg_b" / "__init__.py").write_text("")
    x = tmp_path / "src" / "pkg_a" / "x.py"
    y = tmp_path / "src" / "pkg_b" / "y.py"
    x.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return Bar()\n")
    y.write_text("def existing():\n    return 0\n")

    plan = move_symbols(x, y, ["Foo"], workspace_root=tmp_path)
    assert any(
        "Cross-package move" in w and "cycle detection skipped" in w
        for w in plan.warnings
    )


def test_cycle_detection_runs_after_validate_before_write(
    tmp_path: Path, mocker: pytest.FixtureRequest
) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    spy = mocker.patch("axm_anvil.core.move.batch_edit")
    with pytest.raises(ImportCycleError):
        move_symbols(a, b, ["Foo"], workspace_root=root)
    assert spy.call_count == 0
