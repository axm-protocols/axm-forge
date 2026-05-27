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

from axm_audit.core.fix.findings import collect_unfixable, get_pkg_prefixes
from axm_audit.core.fix.stages_plan import plan_relocate


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


def test_get_pkg_prefixes_reads_deptry_config(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: exposes the first-party package name (deptry-config friendly setup)."""
    pkg = make_pkg(
        pyproject_extras='[tool.deptry]\nknown_first_party = ["mypkg"]\n',
        pkg_name="mypkg",
    )
    assert get_pkg_prefixes(pkg) == {"mypkg"}


def test_get_pkg_prefixes_falls_back_to_src_scan(
    make_pkg: Callable[..., Path],
) -> None:
    """AC2: derives package name by scanning src/ when no deptry config present."""
    pkg = make_pkg(pkg_name="mypkg")
    assert get_pkg_prefixes(pkg) == {"mypkg"}


def test_collect_unfixable_surfaces_no_package_symbol(
    make_pkg: Callable[..., Path],
) -> None:
    """AC4: surfaces TEST_QUALITY_NO_PACKAGE_SYMBOL (NON_DETERMINISTIC_RULES)."""
    pkg = make_pkg(
        files={
            "tests/integration/test_x.py": (
                "def test_x() -> None:\n    assert 1 == 1\n"
            ),
        }
    )
    result = collect_unfixable(pkg)
    assert any(f.get("rule_id") == "TEST_QUALITY_NO_PACKAGE_SYMBOL" for f in result)
