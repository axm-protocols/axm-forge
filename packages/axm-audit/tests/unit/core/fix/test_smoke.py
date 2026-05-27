"""Smoke tests for axm_audit.core.fix public API."""

from __future__ import annotations


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
