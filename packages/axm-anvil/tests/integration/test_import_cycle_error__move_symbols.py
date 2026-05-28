"""Split from ``test_move_cycle_detection.py``."""

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import ImportCycleError


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


def test_cycle_detection_runs_after_validate_before_write(
    tmp_path: Path, mocker: pytest.FixtureRequest
) -> None:
    root, a, b = _setup_cycle_fixture(tmp_path)
    spy = mocker.patch("axm_anvil.core.move.batch_edit")
    with pytest.raises(ImportCycleError):
        move_symbols(a, b, ["Foo"], workspace_root=root)
    assert spy.call_count == 0
