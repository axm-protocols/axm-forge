from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


def _write_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )


def _setup_clean_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return tmp_path, a, b


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


def test_check_mode_returns_plan_without_writing(tmp_path: Path) -> None:
    root, a, b = _setup_clean_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    plan = move_symbols(a, b, ["Foo"], workspace_root=root, check=True)

    assert plan is not None
    assert hasattr(plan, "callers_updated")
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_check_mode_reports_cycle_failure(tmp_path: Path) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
        check=True,
    )

    assert result.success is False
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_check_mode_reports_success_when_clean(tmp_path: Path) -> None:
    root, a, b = _setup_clean_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    tool = MoveTool()
    result = tool.execute(
        path=str(root),
        symbols="Foo",
        from_file=str(a),
        to_file=str(b),
        check=True,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data.get("check") is True
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before
