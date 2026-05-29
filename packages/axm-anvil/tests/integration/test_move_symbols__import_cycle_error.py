"""Cross-package import-cycle detection on move (AXM-1790).

Real two-package uv workspace on disk; ``move_symbols`` must detect a
newly-introduced cross-package import cycle and raise ``ImportCycleError``
(AC3, AC6), and succeed silently for an acyclic cross-package move.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import ImportCycleError

pytestmark = pytest.mark.integration


def _write_workspace(root: Path) -> None:
    """Lay out a two-member uv workspace (pkg_a, pkg_b) under ``root``."""
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


def test_cross_package_move_no_cycle_succeeds(tmp_path: Path) -> None:
    """AC3, AC6: an acyclic cross-package move succeeds, no skip warning."""
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    x = pkg_a / "x.py"
    y = pkg_b / "y.py"
    x.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    y.write_text("def existing():\n    return 0\n")

    plan = move_symbols(x, y, ["Foo"], workspace_root=tmp_path)

    assert "Foo" in plan.moved_names
    assert "def Foo" in y.read_text()
    assert "def Foo" not in x.read_text()
    assert not any("cycle detection skipped" in w for w in plan.warnings), plan.warnings
