"""Smoke tests for axm_audit.core.fix public API."""

from __future__ import annotations

from pathlib import Path


def test_public_api_exports() -> None:
    """AC2: relocated module exposes the same public symbols as the proto."""
    from axm_audit.core.fix import (
        FileOp,
        OpKind,
        PipelineReport,
        format_report,
        run,
    )

    assert run is not None
    assert format_report is not None
    assert FileOp is not None
    assert OpKind is not None
    assert PipelineReport is not None
    assert callable(run)
    assert callable(format_report)


def test_run_on_empty_package_returns_empty_plan(tmp_path: Path) -> None:
    """AC2: pipeline on a package with only an empty tests/ dir yields no ops."""
    from axm_audit.core.fix import run

    (tmp_path / "tests").mkdir()

    report = run(tmp_path)

    assert report.ops == []
    assert report.applied is False
