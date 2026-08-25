"""Unit tests for the pure preflight orchestration core."""

from __future__ import annotations

from axm_edit.core.precheck import check_edit_keys
from axm_edit.core.preflight import merge_diagnostics, partition_diagnostics
from axm_edit.models.check import CheckDiagnostic


def _diagnostic(
    op_index: int,
    code: str,
    message: str,
    severity: str = "error",
) -> CheckDiagnostic:
    """Build an in-memory diagnostic; no path is resolved and no file read."""
    return CheckDiagnostic(
        op_index=op_index,
        file="a.py",
        severity=severity,
        code=code,
        message=message,
        hint="",
    )


def test_merge_diagnostics_orders_by_op_index_then_family_then_message() -> None:
    """AC1: merge_diagnostics yields a deterministic, repeatable order."""
    late = _diagnostic(2, "CREATE_ON_EXISTING", "alpha")
    zeta = _diagnostic(0, "UNKNOWN_EDIT_KEY", "zeta")
    alpha = _diagnostic(0, "UNKNOWN_EDIT_KEY", "alpha")

    merged = merge_diagnostics([late, zeta, alpha])

    assert [(item.op_index, item.message) for item in merged] == [
        (0, "alpha"),
        (0, "zeta"),
        (2, "alpha"),
    ]
    assert merge_diagnostics([late, zeta, alpha]) == merged


def test_partition_diagnostics_splits_errors_and_warnings_in_input_order() -> None:
    """AC2: errors and warnings keep input order and blocking is True."""
    first_warning = _diagnostic(
        0, "LINE_LENGTH_DEFAULT_MISMATCH", "w-first", severity="warning"
    )
    first_error = _diagnostic(1, "CREATE_ON_EXISTING", "e-first")
    second_warning = _diagnostic(
        2, "LINE_LENGTH_DEFAULT_MISMATCH", "w-second", severity="warning"
    )
    second_error = _diagnostic(3, "ANCHOR_NOT_FOUND", "e-second")
    given = [first_warning, first_error, second_warning, second_error]

    report = partition_diagnostics(given)

    assert report.diagnostics == given
    assert report.errors == [first_error, second_error]
    assert report.warnings == [first_warning, second_warning]
    assert report.blocking is True


def test_partition_diagnostics_is_not_blocking_for_warnings_only() -> None:
    """AC2: blocking is False when no diagnostic carries error severity."""
    warnings = [
        _diagnostic(0, "LINE_LENGTH_DEFAULT_MISMATCH", "long", severity="warning"),
        _diagnostic(1, "ANCHOR_AMBIGUOUS", "twice", severity="warning"),
    ]

    report = partition_diagnostics(warnings)

    assert report.blocking is False
    assert report.errors == []
    assert report.warnings == warnings


def test_unknown_edit_key_diagnostic_is_classified_blocking() -> None:
    """AC3: an unknown edit key is a single, blocking diagnostic."""
    diagnostics = check_edit_keys(
        0,
        "a.py",
        {"old": "x", "new": "y", "replace_all": True},
    )

    report = partition_diagnostics(diagnostics)

    assert len(diagnostics) == 1
    assert "replace_all" in diagnostics[0].message
    assert report.blocking is True
    assert report.errors == diagnostics
    assert report.warnings == []
