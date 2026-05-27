"""Unit tests for axm_audit.core.fix.stages_plan — AC5, AC6, AC7."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.fix.stages_plan import plan_flatten, plan_naming, plan_relocate

pytestmark = pytest.mark.integration

_PLAN_CHECK = "axm_audit.core.fix.stages_plan._check_by_rule"


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


def test_plan_flatten_emits_flatten_op_for_heterogeneous_class(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC6: benign heterogeneous Test* class → one FileOp(kind="flatten")."""
    pkg = make_pkg(
        pkg_name="mypkg",
        files={
            "src/mypkg/__init__.py": (
                "def foo() -> None:\n    pass\n\n"
                "def bar() -> None:\n    pass\n\n"
                '__all__ = ["foo", "bar"]\n'
            ),
            "tests/integration/test_x.py": (
                "from mypkg import foo, bar\n\n"
                "class TestX:\n"
                "    def test_one(self) -> None:\n"
                "        foo()\n"
                "    def test_two(self) -> None:\n"
                "        bar()\n"
            ),
        },
    )
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[{"verdict": "SPLIT", "path": str(abs_path)}],
    )
    ops = plan_flatten(pkg)
    flatten_ops = [op for op in ops if not op.rationale.startswith("PATHOLOGICAL")]
    assert len(flatten_ops) == 1
    assert flatten_ops[0].kind == "flatten"
    assert flatten_ops[0].source == abs_path


def test_plan_flatten_marks_pathological_class(
    make_pkg: Callable[..., Path],
    mocker: MockerFixture,
) -> None:
    """AC6: heterogeneous class using self.x → op with PATHOLOGICAL rationale."""
    pkg = make_pkg(
        pkg_name="mypkg",
        files={
            "src/mypkg/__init__.py": (
                "def foo() -> None:\n    pass\n\n"
                "def bar() -> None:\n    pass\n\n"
                '__all__ = ["foo", "bar"]\n'
            ),
            "tests/integration/test_x.py": (
                "from mypkg import foo, bar\n\n"
                "class TestX:\n"
                "    def test_one(self) -> None:\n"
                "        self.x = 1\n"
                "        foo()\n"
                "    def test_two(self) -> None:\n"
                "        bar()\n"
            ),
        },
    )
    abs_path = pkg / "tests" / "integration" / "test_x.py"
    mocker.patch(
        _PLAN_CHECK,
        return_value=[{"verdict": "SPLIT", "path": str(abs_path)}],
    )
    ops = plan_flatten(pkg)
    assert any(op.rationale.startswith("PATHOLOGICAL") for op in ops)


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
