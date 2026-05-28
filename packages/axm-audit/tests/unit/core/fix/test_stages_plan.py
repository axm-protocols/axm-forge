"""Unit tests for axm_audit.core.fix.stages_plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.fix import stages_plan
from axm_audit.core.fix.models import FileOp

_ROOT = Path("/nonexistent-axm-audit-stages-plan-root")

# rule_id -> synthetic findings the patched check_by_rule returns for it.
type FindingMap = dict[str, list[dict[str, Any]]]


def _patch_findings(monkeypatch: pytest.MonkeyPatch, by_rule: FindingMap) -> None:
    """Patch check_by_rule to serve synthetic findings keyed by rule id."""

    def _fake(_project: Path, rule_id: str) -> list[dict[str, Any]]:
        return by_rule.get(rule_id, [])

    monkeypatch.setattr(stages_plan, "check_by_rule", _fake)


# --------------------------------------------------------------------------- #
# plan_relocate
# --------------------------------------------------------------------------- #


def test_plan_relocate_unanimous_file_emits_relocate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file whose every test agrees on a distinct tier yields one relocate op."""
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_PYRAMID_LEVEL": [
                {"path": str(src), "level": "unit"},
                {"path": str(src), "level": "unit"},
            ]
        },
    )
    ops = stages_plan.plan_relocate(_ROOT)
    assert len(ops) == 1
    op = ops[0]
    assert op.kind == "relocate"
    assert op.source == src
    assert op.target == _ROOT / "tests/unit/test_x.py"
    assert "2 test(s)" in op.rationale


def test_plan_relocate_mixed_targets_skips_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file whose tests disagree on the target tier is left untouched."""
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_PYRAMID_LEVEL": [
                {"path": str(src), "level": "unit"},
                {"path": str(src), "level": "e2e"},
            ]
        },
    )
    assert stages_plan.plan_relocate(_ROOT) == []


def test_plan_relocate_already_correct_tier_skips_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the unanimous target equals the current tier, no op is emitted."""
    src = _ROOT / "tests/unit/test_x.py"
    _patch_findings(
        monkeypatch,
        {"TEST_QUALITY_PYRAMID_LEVEL": [{"path": str(src), "level": "unit"}]},
    )
    assert stages_plan.plan_relocate(_ROOT) == []


def test_plan_relocate_ignores_findings_without_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Findings lacking a 'level' key contribute nothing to the plan."""
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {"TEST_QUALITY_PYRAMID_LEVEL": [{"path": str(src)}]},
    )
    assert stages_plan.plan_relocate(_ROOT) == []


def test_plan_relocate_empty_findings_yields_no_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pyramid findings means no relocate ops."""
    _patch_findings(monkeypatch, {})
    assert stages_plan.plan_relocate(_ROOT) == []


# --------------------------------------------------------------------------- #
# plan_naming — splits
# --------------------------------------------------------------------------- #


def test_plan_naming_split_emits_split_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SPLIT finding on a canonical-tier file yields a split op with targets."""
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(src),
                    "verdict": "SPLIT",
                    "suggested_splits": ["test_a__b.py", "test_c__d.py"],
                    "split_map": {"test_a__b.py": ["test_a"]},
                }
            ]
        },
    )
    splits, merges, renames = stages_plan.plan_naming(_ROOT)
    assert merges == [] and renames == []
    assert len(splits) == 1
    op = splits[0]
    assert op.kind == "split"
    assert op.source == src
    assert op.target == [src.parent / "test_a__b.py", src.parent / "test_c__d.py"]
    assert op.split_map == {"test_a__b.py": ["test_a"]}


def test_plan_naming_split_drops_unknown_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 'test_UNKNOWN.py' suggested split is filtered from the targets."""
    src = _ROOT / "tests/e2e/test_x.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(src),
                    "verdict": "SPLIT",
                    "suggested_splits": ["test_keep.py", "test_UNKNOWN.py"],
                }
            ]
        },
    )
    splits, _, _ = stages_plan.plan_naming(_ROOT)
    assert splits[0].target == [src.parent / "test_keep.py"]


def test_plan_naming_split_skips_non_canonical_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SPLIT finding on a unit-tier file is ignored (not canonical for naming)."""
    src = _ROOT / "tests/unit/test_x.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(src),
                    "verdict": "SPLIT",
                    "suggested_splits": ["test_a__b.py"],
                }
            ]
        },
    )
    splits, merges, renames = stages_plan.plan_naming(_ROOT)
    assert (splits, merges, renames) == ([], [], [])


# --------------------------------------------------------------------------- #
# plan_naming — merges
# --------------------------------------------------------------------------- #


def test_plan_naming_collide_merges_into_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A COLLIDE finding merges every non-anchor file into the sorted-first file."""
    a = _ROOT / "tests/integration/test_a.py"
    b = _ROOT / "tests/integration/test_b.py"
    c = _ROOT / "tests/integration/test_c.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "verdict": "COLLIDE",
                    "files": [str(c), str(a), str(b)],
                    "canonical_name": "test_x__y.py",
                    "tier": "integration",
                }
            ]
        },
    )
    _, merges, _ = stages_plan.plan_naming(_ROOT)
    assert len(merges) == 2
    assert {m.kind for m in merges} == {"merge"}
    assert all(m.target == a for m in merges)
    assert {m.source for m in merges} == {b, c}


def test_plan_naming_collide_single_file_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A COLLIDE finding with fewer than two files yields no merge op."""
    a = _ROOT / "tests/integration/test_a.py"
    _patch_findings(
        monkeypatch,
        {"TEST_QUALITY_FILE_NAMING": [{"verdict": "COLLIDE", "files": [str(a)]}]},
    )
    _, merges, _ = stages_plan.plan_naming(_ROOT)
    assert merges == []


def test_plan_naming_collide_skips_non_canonical_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A COLLIDE group containing a unit-tier file is skipped wholesale."""
    a = _ROOT / "tests/integration/test_a.py"
    b = _ROOT / "tests/unit/test_b.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {"verdict": "COLLIDE", "files": [str(a), str(b)]}
            ]
        },
    )
    _, merges, _ = stages_plan.plan_naming(_ROOT)
    assert merges == []


# --------------------------------------------------------------------------- #
# plan_naming — renames
# --------------------------------------------------------------------------- #


def test_plan_naming_name_mismatch_emits_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NAME_MISMATCH finding yields a rename to the proposed canonical name."""
    src = _ROOT / "tests/integration/test_old.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(src),
                    "verdict": "NAME_MISMATCH",
                    "proposed_name": "test_new__sym.py",
                }
            ]
        },
    )
    _, _, renames = stages_plan.plan_naming(_ROOT)
    assert len(renames) == 1
    op = renames[0]
    assert op.kind == "rename"
    assert op.source == src
    assert op.target == src.parent / "test_new__sym.py"


@pytest.mark.parametrize(
    "proposed",
    ["", "test_old.py", "test_UNKNOWN.py"],
    ids=["empty", "same-name", "unknown"],
)
def test_plan_naming_rename_no_op_proposals_are_skipped(
    monkeypatch: pytest.MonkeyPatch, proposed: str
) -> None:
    """Empty, identical or UNKNOWN proposed names produce no rename op."""
    src = _ROOT / "tests/integration/test_old.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(src),
                    "verdict": "NAME_MISMATCH",
                    "proposed_name": proposed,
                }
            ]
        },
    )
    _, _, renames = stages_plan.plan_naming(_ROOT)
    assert renames == []


def test_plan_naming_empty_findings_yields_three_empty_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No FILE_NAMING findings means empty splits, merges and renames."""
    _patch_findings(monkeypatch, {})
    assert stages_plan.plan_naming(_ROOT) == ([], [], [])


# --------------------------------------------------------------------------- #
# plan_flatten
# --------------------------------------------------------------------------- #


def _patch_flatten_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise plan_flatten's prefix/script collaborators (no disk)."""
    monkeypatch.setattr(stages_plan, "get_pkg_prefixes", lambda _p: ("axm_audit",))
    monkeypatch.setattr(stages_plan, "load_project_scripts", lambda _p: {})


def test_plan_flatten_nonexistent_candidates_yield_no_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FLATTEN findings on non-existent paths collect no candidates → no ops."""
    _patch_flatten_env(monkeypatch)
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {"TEST_QUALITY_FILE_NAMING": [{"path": str(src), "verdict": "SPLIT"}]},
    )
    assert stages_plan.plan_flatten(_ROOT) == []


def test_plan_flatten_non_flatten_verdict_yields_no_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finding whose verdict is outside the flatten set is ignored."""
    _patch_flatten_env(monkeypatch)
    src = _ROOT / "tests/integration/test_x.py"
    _patch_findings(
        monkeypatch,
        {"TEST_QUALITY_FILE_NAMING": [{"path": str(src), "verdict": "OK"}]},
    )
    assert stages_plan.plan_flatten(_ROOT) == []


def test_plan_flatten_empty_findings_yields_no_ops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No FILE_NAMING findings means no flatten ops."""
    _patch_flatten_env(monkeypatch)
    _patch_findings(monkeypatch, {})
    assert stages_plan.plan_flatten(_ROOT) == []


# --------------------------------------------------------------------------- #
# return-type contract
# --------------------------------------------------------------------------- #


def test_plan_naming_returns_three_distinct_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plan_naming groups by verdict into independent split/merge/rename lists."""
    split_src = _ROOT / "tests/integration/test_s.py"
    rename_src = _ROOT / "tests/integration/test_old.py"
    _patch_findings(
        monkeypatch,
        {
            "TEST_QUALITY_FILE_NAMING": [
                {
                    "path": str(split_src),
                    "verdict": "SPLIT",
                    "suggested_splits": ["test_a__b.py"],
                },
                {
                    "path": str(rename_src),
                    "verdict": "NAME_MISMATCH",
                    "proposed_name": "test_new__sym.py",
                },
            ]
        },
    )
    splits, merges, renames = stages_plan.plan_naming(_ROOT)
    assert [op.kind for op in splits] == ["split"]
    assert merges == []
    assert [op.kind for op in renames] == ["rename"]
    assert all(isinstance(op, FileOp) for op in (*splits, *renames))
