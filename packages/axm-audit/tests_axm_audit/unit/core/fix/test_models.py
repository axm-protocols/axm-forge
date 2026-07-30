"""Unit tests for axm_audit.core.fix.models — AC1."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.fix.models import (
    CANONICAL_TIERS,
    MAX_ITERATIONS,
    NON_DETERMINISTIC_RULES,
    TOP_K,
    FileOp,
    PipelineReport,
)


def test_fileop_default_split_map_none() -> None:
    """AC1: FileOp.split_map defaults to None for non-split kinds."""
    op = FileOp(
        kind="rename",
        source=Path("a"),
        target=Path("b"),
        rationale="r",
        source_rule="X",
    )
    assert op.split_map is None


def test_pipeline_report_by_kind_counts() -> None:
    """AC1: PipelineReport.by_kind aggregates op counts grouped by kind."""
    ops = [
        FileOp(
            kind="relocate",
            source=Path("a"),
            target=Path("b"),
            rationale="",
            source_rule="X",
        ),
        FileOp(
            kind="relocate",
            source=Path("c"),
            target=Path("d"),
            rationale="",
            source_rule="X",
        ),
        FileOp(
            kind="split",
            source=Path("e"),
            target=[Path("f")],
            rationale="",
            source_rule="X",
        ),
        FileOp(
            kind="rename",
            source=Path("g"),
            target=Path("h"),
            rationale="",
            source_rule="X",
        ),
    ]
    report = PipelineReport(ops=ops)
    assert report.by_kind() == {"relocate": 2, "split": 1, "rename": 1}


def test_non_deterministic_rules_contains_no_package_symbol() -> None:
    """AC1: NON_DETERMINISTIC_RULES surfaces TEST_QUALITY_NO_PACKAGE_SYMBOL."""
    assert "TEST_QUALITY_NO_PACKAGE_SYMBOL" in NON_DETERMINISTIC_RULES


def test_constants_values() -> None:
    """AC1: module constants hold their documented values."""
    assert MAX_ITERATIONS == 6
    assert TOP_K == 2
    assert CANONICAL_TIERS == frozenset({"unit", "integration", "e2e"})
