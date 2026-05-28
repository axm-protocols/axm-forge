"""Unit tests for axm_audit.core.fix.stages_plan — AC5, AC6, AC7."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.fix.stages_plan import plan_naming
from tests.integration._helpers import _PLAN_CHECK

pytestmark = pytest.mark.integration


def test_plan_naming_split_filters_unit_tier(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC7: SPLIT verdicts in unit/ tier are filtered out (B2 defensive)."""
    pkg = make_pkg()
    abs_path = pkg / "tests" / "unit" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[
            {
                "verdict": "SPLIT",
                "path": str(abs_path),
                "suggested_splits": ["test_a.py"],
            },
        ],
    )
    splits, _merges, _renames = plan_naming(pkg)
    assert splits == []


def test_plan_naming_collide_anchor_is_lexically_first(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC7: COLLIDE picks the lexically-first file as the merge anchor."""
    pkg = make_pkg()
    path_z = pkg / "tests" / "integration" / "test_z.py"
    path_a = pkg / "tests" / "integration" / "test_a.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[
            {
                "verdict": "COLLIDE",
                "files": [str(path_z), str(path_a)],
                "canonical_name": "test_a.py",
                "tier": "integration",
            },
        ],
    )
    _splits, merges, _renames = plan_naming(pkg)
    assert len(merges) == 1
    target = merges[0].target
    assert isinstance(target, Path)
    assert target.name == "test_a.py"


def test_plan_naming_rename_skips_split_consumed_files(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC7: RENAME skips files already consumed by SPLIT for the same path."""
    pkg = make_pkg()
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[
            {
                "verdict": "SPLIT",
                "path": str(abs_path),
                "suggested_splits": ["test_a.py", "test_b.py"],
            },
            {
                "verdict": "NAME_MISMATCH",
                "path": str(abs_path),
                "proposed_name": "test_y.py",
            },
        ],
    )
    _splits, _merges, renames = plan_naming(pkg)
    assert all(op.source != abs_path for op in renames)
