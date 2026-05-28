"""Integration tests for FileNamingRule canonical-name helper.

Uses real-filesystem fixtures.
"""

from __future__ import annotations

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


def test_compute_canonical_name_returns_none_for_unit_tier(tmp_path: Path) -> None:
    """AC4: unit-tier test files are out of scope → helper returns None."""
    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    test_file = tmp_path / "tests" / "unit" / "test_x.py"
    _write(
        test_file,
        "from pkg.foo import foo\n\ndef test_x():\n    assert foo() == 1\n",
    )

    assert compute_canonical_name(test_file, tmp_path) is None


def test_compute_canonical_name_returns_none_when_no_symbols(tmp_path: Path) -> None:
    """AC4: integration file with no first-party symbol coverage → None."""
    _mk_pkg(tmp_path)
    test_file = tmp_path / "tests" / "integration" / "test_foo.py"
    _write(test_file, "def test_x():\n    pass\n")

    assert compute_canonical_name(test_file, tmp_path) is None
