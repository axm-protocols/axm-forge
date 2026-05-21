"""Unit tests for axm_audit.core.fix.report — AC4."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.fix.models import FileOp, PipelineReport
from axm_audit.core.fix.report import _fmt_target, format_report


def _make_op(kind: str = "relocate") -> FileOp:
    return FileOp(
        kind=kind,
        source=Path("/p/src/a.py"),
        target=Path("/p/src/b.py"),
        rationale="r",
        source_rule="X",
    )


def test_empty_plan_renders_no_ops_message() -> None:
    """AC4: empty PipelineReport shows no-ops banner and zero findings."""
    report = PipelineReport()
    out = format_report(report, Path("/p"))
    assert "(no deterministic ops planned)" in out
    assert "Out of pipeline: 0 finding" in out


def test_kind_counts_section() -> None:
    """AC4: per-kind counts render with the documented header format."""
    ops = [_make_op("relocate") for _ in range(3)] + [
        _make_op("rename") for _ in range(2)
    ]
    report = PipelineReport(ops=ops)
    out = format_report(report, Path("/p"))
    assert "Stage RELOCATE  3 op(s)" in out
    assert "Stage RENAME    2 op(s)" in out


def test_ops_truncation_above_30() -> None:
    """AC4: more than 30 ops yields a `... +N more` truncation marker."""
    ops = [_make_op("relocate") for _ in range(35)]
    report = PipelineReport(ops=ops)
    out = format_report(report, Path("/p"))
    assert "... +5 more" in out


def test_unfixable_and_warnings_sections() -> None:
    """AC4: unfixable and warnings sections render with header counts."""
    report = PipelineReport(
        unfixable=[
            {
                "rule_id": "TEST_QUALITY_NO_PACKAGE_SYMBOL",
                "test_file": "tests/test_a.py",
            }
        ],
        warnings=["something happened"],
    )
    out = format_report(report, Path("/p"))
    assert "Out of pipeline (agent-driven" in out
    assert "Warnings (1):" in out


def test_fmt_target_list_and_path() -> None:
    """AC4: _fmt_target formats single Path and list[Path] inputs relative to root."""
    root = Path("/p")
    assert _fmt_target(Path("/p/tests/unit/test_a.py"), root) == "tests/unit/test_a.py"
    paths = [Path("/p/tests/unit/a.py"), Path("/p/tests/unit/b.py")]
    assert _fmt_target(paths, root) == "tests/unit/a.py, tests/unit/b.py"
