"""Split from ``test_move_cycle_detection.py``."""

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import ImportCycleError
from tests.integration._helpers import (
    _write_pyproject__from_move_cycle_detection,
    _write_workspace,
)


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


def test_move_cross_package_detects_cycle(tmp_path: Path) -> None:
    """AC3, AC6 (contract inverted from skip): a cross-package move that
    introduces a new import cycle now raises ``ImportCycleError`` and no
    longer emits the obsolete \"cycle detection skipped\" warning.

    ``pkg_a.x`` imports ``Thing`` from ``pkg_b.y`` (edge pkg_a.x -> pkg_b.y).
    Moving ``Foo`` (uses ``Bar``, which stays in pkg_a.x) into ``pkg_b.y``
    adds edge pkg_b.y -> pkg_a.x, closing the cycle.
    """
    root = tmp_path
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/pkg_a", "packages/pkg_b"]\n'
    )
    for name in ("pkg_a", "pkg_b"):
        member = root / "packages" / name
        pkg = member / "src" / name
        pkg.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
        )
        (pkg / "__init__.py").write_text("")
    x = root / "packages" / "pkg_a" / "src" / "pkg_a" / "x.py"
    y = root / "packages" / "pkg_b" / "src" / "pkg_b" / "y.py"
    x.write_text(
        "from pkg_b.y import Thing\n\n"
        "def Bar():\n    return 1\n\n"
        "def use_thing():\n    return Thing()\n\n"
        "def Foo():\n    return Bar()\n"
    )
    y.write_text("def Thing():\n    return 0\n")

    with pytest.raises(ImportCycleError):
        move_symbols(x, y, ["Foo"], workspace_root=root)


def test_intra_package_cycle_detection_unchanged(tmp_path: Path) -> None:
    """AC5: intra-package cycle detection is strictly unchanged (regression).

    Moving ``Foo`` from ``mypkg.a`` to ``mypkg.b`` where ``a`` already imports
    ``helper`` from ``b`` closes a same-package cycle and must raise.
    """
    _write_pyproject__from_move_cycle_detection(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text(
        "from mypkg.b import helper\n\n"
        "def Bar():\n    return 1\n\n"
        "def uses_helper():\n    return helper()\n\n"
        "def Foo():\n    return Bar()\n"
    )
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")

    with pytest.raises(ImportCycleError):
        move_symbols(a, b, ["Foo"], workspace_root=tmp_path)


def test_cross_package_move_introducing_cycle_raises(tmp_path: Path) -> None:
    """AC3, AC6: a cross-package move that creates a new import cycle raises.

    ``pkg_a.x`` already imports from ``pkg_b.y`` (edge pkg_a.x -> pkg_b.y).
    Moving ``Foo`` (which uses ``Bar``, staying in pkg_a.x) into ``pkg_b.y``
    introduces edge pkg_b.y -> pkg_a.x, closing the cycle.
    """
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    x = pkg_a / "x.py"
    y = pkg_b / "y.py"
    x.write_text(
        "from pkg_b.y import Thing\n"
        "\n"
        "def Bar():\n"
        "    return 1\n"
        "\n"
        "def use_thing():\n"
        "    return Thing()\n"
        "\n"
        "def Foo():\n"
        "    return Bar()\n"
    )
    y.write_text("def Thing():\n    return 0\n")
    x_before = x.read_bytes()
    y_before = y.read_bytes()

    with pytest.raises(ImportCycleError):
        move_symbols(x, y, ["Foo"], workspace_root=tmp_path)

    # No mutation on the rejected move.
    assert x.read_bytes() == x_before
    assert y.read_bytes() == y_before
