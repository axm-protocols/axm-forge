"""Unit tests for axm_audit.core.fix.findings adapter — AC1, AC2, AC4.

The AC1 tests (formerly hitting the private ``_check_by_rule`` adapter)
are lifted to ``plan_relocate``, the natural public consumer in
``core.fix.stages_plan``: it derives a ``FileOp`` with ``kind='relocate'``
directly from the ``path`` + ``level`` keys of each PYRAMID_LEVEL
finding, so a green ``FileOp`` proves the underlying adapter wired the
finding shape correctly. The AC3 test on ``_load_project_scripts`` is
retired: the duplicate has been replaced by the canonical
``axm_audit.core.rules.test_quality._shared.load_project_scripts``,
whose contract is already exercised by
``tests/integration/test_has_in_package_subprocess_invocation__load_project_scripts.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.fix.stages_plan import plan_relocate
from tests.integration._helpers import _PLAN_CHECK

pytestmark = pytest.mark.integration


def test_plan_relocate_emits_op_for_mis_tiered_test(
    make_pkg: Callable[..., Path],
) -> None:
    """AC1: a mis-tiered integration test surfaces as a relocate ``FileOp``.

    ``plan_relocate`` is the canonical consumer of PYRAMID_LEVEL findings:
    a green ``FileOp(kind='relocate')`` proves the underlying adapter
    returned ``list[dict]`` carrying both ``path`` and ``level`` keys.
    """
    pkg = make_pkg(
        files={
            "tests/integration/test_x.py": (
                "def test_x() -> None:\n    assert 1 == 1\n"
            ),
        }
    )
    ops = plan_relocate(pkg)
    assert ops, "expected at least one relocate op for mis-tiered integration test"
    op = ops[0]
    assert op.kind == "relocate"
    assert isinstance(op.source, Path)
    assert "integration" in op.source.parts
    assert isinstance(op.target, Path)
    assert "unit" in op.target.parts
    assert op.source_rule == "TEST_QUALITY_PYRAMID_LEVEL"


def test_plan_relocate_empty_when_clean(
    make_pkg: Callable[..., Path],
) -> None:
    """AC1: no PYRAMID_LEVEL finding ⇒ no relocate op."""
    pkg = make_pkg()
    assert plan_relocate(pkg) == []


def test_plan_relocate_unanimous_emits_one_op(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC5: unanimous target-tier classification → exactly one relocate op."""
    pkg = make_pkg()
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[
            {"path": str(abs_path), "level": "unit"},
            {"path": str(abs_path), "level": "unit"},
        ],
    )
    ops = plan_relocate(pkg)
    assert len(ops) == 1
    assert ops[0].kind == "relocate"
    assert ops[0].source == abs_path


def test_plan_relocate_mixed_tiers_emits_zero_ops(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC5: mixed-tier findings on one file → zero ops (B3 oscillation guard)."""
    pkg = make_pkg()
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[
            {"path": str(abs_path), "level": "unit"},
            {"path": str(abs_path), "level": "e2e"},
        ],
    )
    assert plan_relocate(pkg) == []
