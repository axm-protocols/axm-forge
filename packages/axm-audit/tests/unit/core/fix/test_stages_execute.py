"""Unit tests for axm_audit.core.fix.stages_execute."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import (
    execute,
    execute_flatten,
    execute_merge,
    execute_split,
    reroute_through_safe_move,
)

# Paths that are guaranteed not to exist on disk; the guard branches under
# test all key on ``Path.exists()`` returning ``False``, so no real I/O is
# performed (keeps these tests at the unit pyramid level).
_ABSENT_ROOT = Path("/nonexistent-axm-audit-test-root")


def _make_op(
    kind: str,
    source: Path,
    target: Path | list[Path],
    *,
    split_map: dict[str, list[str]] | None = None,
) -> FileOp:
    return FileOp(
        kind=kind,
        source=source,
        target=target,
        rationale="r",
        source_rule="X",
        split_map=split_map,
    )


def test_flatten_skipped_when_split_map_none() -> None:
    """_execute_flatten bails with the rationale message when split_map is None."""
    op = _make_op(
        "flatten", _ABSENT_ROOT / "tests/integration/test_x.py", _ABSENT_ROOT / "x"
    )
    msgs = execute_flatten(op, _ABSENT_ROOT)
    assert msgs == ["flatten skipped: r (test_x.py)"]


def test_flatten_skipped_when_source_missing() -> None:
    """_execute_flatten skips when split_map is set but the source file is absent."""
    missing = _ABSENT_ROOT / "test_gone.py"
    op = _make_op("flatten", missing, _ABSENT_ROOT / "x", split_map={"TestA": ["t"]})
    msgs = execute_flatten(op, _ABSENT_ROOT)
    assert msgs == [f"flatten skipped: {missing} missing"]


def test_merge_skipped_when_source_or_target_missing() -> None:
    """_execute_merge skips when either endpoint file does not exist."""
    src = _ABSENT_ROOT / "test_src.py"
    tgt = _ABSENT_ROOT / "test_tgt.py"
    op = _make_op("merge", src, tgt)
    msgs = execute_merge(op, _ABSENT_ROOT)
    assert msgs == [f"merge skipped: missing ({src} -> {tgt})"]


def test_reroute_skipped_when_source_missing() -> None:
    """_reroute_through_safe_move skips when the source file is absent."""
    src = _ABSENT_ROOT / "test_src.py"
    tgt = _ABSENT_ROOT / "test_tgt.py"
    msgs = reroute_through_safe_move("relocate", src, tgt, _ABSENT_ROOT)
    assert msgs == [f"relocate skipped: source missing ({src})"]


@pytest.mark.parametrize(
    ("rel_path", "expected_reason"),
    [
        pytest.param(
            "tests/unit/test_x.py",
            "source not under tests/integration|e2e",
            id="non-canonical-tier",
        ),
        pytest.param(
            "tests/integration/test_x.py",
            "source missing",
            id="integration-source-absent",
        ),
    ],
)
def test_split_skipped_with_reason(rel_path: str, expected_reason: str) -> None:
    """_execute_split skips with the guard-specific reason (bad-tier vs missing)."""
    src = _ABSENT_ROOT / rel_path
    op = _make_op("split", src, [src])
    msgs = execute_split(op, _ABSENT_ROOT)
    assert msgs == [f"split skipped: {expected_reason} ({src})"]


def _single_flatten_ops() -> list[FileOp]:
    return [
        _make_op(
            "flatten", _ABSENT_ROOT / "tests/integration/test_x.py", _ABSENT_ROOT / "x"
        )
    ]


def _split_and_merge_ops() -> list[FileOp]:
    split_src = _ABSENT_ROOT / "tests/integration/test_a.py"
    merge_src = _ABSENT_ROOT / "test_b.py"
    merge_tgt = _ABSENT_ROOT / "test_c.py"
    return [
        _make_op("split", split_src, [split_src]),
        _make_op("merge", merge_src, merge_tgt),
    ]


def _two_flatten_ops() -> list[FileOp]:
    return [
        _make_op(
            "flatten", _ABSENT_ROOT / "tests/integration/test_a.py", _ABSENT_ROOT / "a"
        ),
        _make_op(
            "flatten", _ABSENT_ROOT / "tests/integration/test_b.py", _ABSENT_ROOT / "b"
        ),
    ]


@pytest.mark.parametrize(
    ("ops_factory", "expected_warnings"),
    [
        pytest.param(
            _single_flatten_ops,
            ["flatten skipped: r (test_x.py)"],
            id="dispatch-flatten",
        ),
        pytest.param(
            _split_and_merge_ops,
            [
                f"split skipped: source missing "
                f"({_ABSENT_ROOT / 'tests/integration/test_a.py'})",
                f"merge skipped: missing "
                f"({_ABSENT_ROOT / 'test_b.py'} -> {_ABSENT_ROOT / 'test_c.py'})",
            ],
            id="route-split-and-merge",
        ),
        pytest.param(
            _two_flatten_ops,
            [
                "flatten skipped: r (test_a.py)",
                "flatten skipped: r (test_b.py)",
            ],
            id="aggregate-across-ops",
        ),
    ],
)
def test_execute_routes_and_aggregates_warnings(
    ops_factory: Callable[[], list[FileOp]], expected_warnings: list[str]
) -> None:
    """execute() dispatches each kind to its executor and aggregates warnings."""
    # Verifies that warnings are returned in order.
    warnings = execute(ops_factory(), _ABSENT_ROOT)
    assert warnings == expected_warnings


def test_execute_ignores_unknown_kind() -> None:
    """execute() silently no-ops on an op whose kind matches no stage."""
    op = _make_op("noop", _ABSENT_ROOT / "x.py", _ABSENT_ROOT / "y.py")
    assert execute([op], _ABSENT_ROOT) == []
