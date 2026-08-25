"""Integration tests for execute split routing (real fs + git + libcst + anvil)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute_split

pytestmark = pytest.mark.integration


def _op(
    kind: str,
    source: Path,
    target: Path | list[Path],
    *,
    split_map: dict[str, list[str]] | None = None,
) -> FileOp:
    return FileOp(
        kind=kind,
        source=source,
        target=target,
        rationale="r",
        source_rule="X",
        split_map=split_map,
    )


def test_execute_split_skipped_when_no_movable_units(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """SPLIT skips when the source has no top-level test units to route."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_x.py": '"""nothing movable."""\nCONST = 1\n',
        }
    )
    src = pkg / "tests/integration/test_x.py"

    warnings = execute_split(_op("split", src, [src]), pkg)

    assert warnings == [f"split skipped: no movable units in {src}"]
    assert src.exists()


def test_execute_split_skipped_when_cohesive_single_group(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """SPLIT skips when every unit routes to one canonical name (<2 groups)."""
    pkg = make_test_pkg(
        {
            "src/pkg/a.py": "def a():\n    return 1\n",
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_a.py": (
                "from pkg.a import a\n\n"
                "def test_one():\n    assert a() == 1\n\n"
                "def test_two():\n    assert a() == 1\n"
            ),
        }
    )
    src = pkg / "tests/integration/test_a.py"

    warnings = execute_split(_op("split", src, [src]), pkg)

    assert warnings == [
        "split skipped: test_a.py has <2 unit-groups "
        "(file is cohesive at canonical-name level)"
    ]
    assert src.exists()
