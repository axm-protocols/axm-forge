"""Unit tests for axm_audit.core.fix.stages_execute."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import (
    _execute_flatten,
    _execute_merge,
    _execute_split,
    _reroute_through_safe_move,
    execute,
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
    msgs = _execute_flatten(op, _ABSENT_ROOT)
    assert msgs == ["flatten skipped: r (test_x.py)"]


def test_flatten_skipped_when_source_missing() -> None:
    """_execute_flatten skips when split_map is set but the source file is absent."""
    missing = _ABSENT_ROOT / "test_gone.py"
    op = _make_op("flatten", missing, _ABSENT_ROOT / "x", split_map={"TestA": ["t"]})
    msgs = _execute_flatten(op, _ABSENT_ROOT)
    assert msgs == [f"flatten skipped: {missing} missing"]


def test_merge_skipped_when_source_or_target_missing() -> None:
    """_execute_merge skips when either endpoint file does not exist."""
    src = _ABSENT_ROOT / "test_src.py"
    tgt = _ABSENT_ROOT / "test_tgt.py"
    op = _make_op("merge", src, tgt)
    msgs = _execute_merge(op, _ABSENT_ROOT)
    assert msgs == [f"merge skipped: missing ({src} -> {tgt})"]


def test_reroute_skipped_when_source_missing() -> None:
    """_reroute_through_safe_move skips when the source file is absent."""
    src = _ABSENT_ROOT / "test_src.py"
    tgt = _ABSENT_ROOT / "test_tgt.py"
    msgs = _reroute_through_safe_move("relocate", src, tgt, _ABSENT_ROOT)
    assert msgs == [f"relocate skipped: source missing ({src})"]


def test_split_skipped_when_source_not_integration_or_e2e() -> None:
    """_execute_split skips when the source is not under integration|e2e."""
    src = _ABSENT_ROOT / "tests/unit/test_x.py"
    op = _make_op("split", src, [src])
    msgs = _execute_split(op, _ABSENT_ROOT)
    assert msgs == [f"split skipped: source not under tests/integration|e2e ({src})"]


def test_split_skipped_when_source_missing() -> None:
    """_execute_split skips when an integration source path is absent."""
    src = _ABSENT_ROOT / "tests/integration/test_x.py"
    op = _make_op("split", src, [src])
    msgs = _execute_split(op, _ABSENT_ROOT)
    assert msgs == [f"split skipped: source missing ({src})"]


def test_execute_dispatches_each_kind_to_its_executor() -> None:
    """execute() routes flatten ops to _execute_flatten and aggregates warnings."""
    op = _make_op(
        "flatten", _ABSENT_ROOT / "tests/integration/test_x.py", _ABSENT_ROOT / "x"
    )
    warnings = execute([op], _ABSENT_ROOT)
    assert warnings == ["flatten skipped: r (test_x.py)"]


def test_execute_routes_split_and_merge_kinds() -> None:
    """execute() dispatches split and merge ops to their respective executors."""
    split_src = _ABSENT_ROOT / "tests/integration/test_a.py"
    split_op = _make_op("split", split_src, [split_src])
    merge_src = _ABSENT_ROOT / "test_b.py"
    merge_tgt = _ABSENT_ROOT / "test_c.py"
    merge_op = _make_op("merge", merge_src, merge_tgt)
    warnings = execute([split_op, merge_op], _ABSENT_ROOT)
    assert warnings == [
        f"split skipped: source missing ({split_src})",
        f"merge skipped: missing ({merge_src} -> {merge_tgt})",
    ]


def test_execute_aggregates_warnings_across_ops() -> None:
    """execute() concatenates warnings from multiple ops in submission order."""
    op_a = _make_op(
        "flatten", _ABSENT_ROOT / "tests/integration/test_a.py", _ABSENT_ROOT / "a"
    )
    op_b = _make_op(
        "flatten", _ABSENT_ROOT / "tests/integration/test_b.py", _ABSENT_ROOT / "b"
    )
    warnings = execute([op_a, op_b], _ABSENT_ROOT)
    assert warnings == [
        "flatten skipped: r (test_a.py)",
        "flatten skipped: r (test_b.py)",
    ]


def test_execute_ignores_unknown_kind() -> None:
    """execute() silently no-ops on an op whose kind matches no stage."""
    op = _make_op("noop", _ABSENT_ROOT / "x.py", _ABSENT_ROOT / "y.py")
    assert execute([op], _ABSENT_ROOT) == []
