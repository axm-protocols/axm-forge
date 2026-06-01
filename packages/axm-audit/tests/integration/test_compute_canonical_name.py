"""Integration tests for FileNamingRule canonical-name helper.

Uses real-filesystem fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.file_naming import (
    compute_canonical_name,
)
from tests.integration._helpers import _mk_pkg

pytestmark = pytest.mark.integration


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _seed_unit_tier(tmp_path: Path) -> Path:
    """Unit-tier test exercising a first-party symbol (out of scope)."""
    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    test_file = tmp_path / "tests" / "unit" / "test_x.py"
    _write(
        test_file,
        "from pkg.foo import foo\n\ndef test_x():\n    assert foo() == 1\n",
    )
    return test_file


def _seed_integration_no_symbols(tmp_path: Path) -> Path:
    """Integration-tier test covering no first-party symbol."""
    _mk_pkg(tmp_path)
    test_file = tmp_path / "tests" / "integration" / "test_foo.py"
    _write(test_file, "def test_x():\n    pass\n")
    return test_file


@pytest.mark.parametrize(
    "seed",
    [
        pytest.param(_seed_unit_tier, id="unit-tier-out-of-scope"),
        pytest.param(_seed_integration_no_symbols, id="no-symbols-covered"),
    ],
)
def test_compute_canonical_name_returns_none(
    tmp_path: Path,
    seed: Callable[[Path], Path],
) -> None:
    """AC4: helper returns None for out-of-scope unit tiers and symbol-less files."""
    test_file = seed(tmp_path)
    assert compute_canonical_name(test_file, tmp_path) is None
