"""Integration tests for reroute_through_safe_move (real fs + git + libcst + anvil)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.stages_execute import reroute_through_safe_move

pytestmark = pytest.mark.integration


def test_reroute_through_safe_move_rewrites_cross_imports(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """reroute_through_safe_move moves units, deletes source, fixes sibling imports."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/e2e/__init__.py": "",
            "tests/integration/test_old.py": (
                "def shared():\n    return 7\n\n"
                "def test_old():\n    assert shared() == 7\n"
            ),
            "tests/integration/test_new.py": "def test_existing():\n    assert True\n",
            "tests/e2e/test_dep.py": (
                "from tests.integration.test_old import shared\n\n"
                "def test_dep():\n    assert shared() == 7\n"
            ),
        }
    )
    src = pkg / "tests/integration/test_old.py"
    tgt = pkg / "tests/integration/test_new.py"

    warnings = reroute_through_safe_move("relocate", src, tgt, pkg)

    assert not src.exists()
    assert "def test_old():" in tgt.read_text()
    assert any("rewrote import in tests/e2e/test_dep.py" in w for w in warnings)
    assert (
        "from tests.integration.test_new import shared"
        in (pkg / "tests/e2e/test_dep.py").read_text()
    )
