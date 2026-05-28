"""Unit tests for axm_audit.core.fix.stages_plan pure planning helpers."""

from __future__ import annotations

from pathlib import Path

from axm_audit.core.fix.stages_plan import (
    _add_existing_abs,
    _collect_flatten_candidates,
    _is_canonical_tier,
    _merge_ops_from_finding,
    _split_op_from_finding,
)

# ---------------------------------------------------------------------------
# _add_existing_abs
# ---------------------------------------------------------------------------


def test_add_existing_abs_adds_absolute_existing_path(tmp_path: Path) -> None:
    """An absolute, existing path is added to the target set."""
    f = tmp_path / "f.py"
    f.write_text("")
    target: set[Path] = set()
    _add_existing_abs(target, str(f))
    assert target == {f}


def test_add_existing_abs_skips_relative_paths(tmp_path: Path) -> None:
    """Relative paths are silently ignored."""
    target: set[Path] = set()
    _add_existing_abs(target, "tests/relative.py")
    assert target == set()


def test_add_existing_abs_skips_missing_paths(tmp_path: Path) -> None:
    """Absolute but non-existent paths are ignored."""
    target: set[Path] = set()
    _add_existing_abs(target, str(tmp_path / "ghost.py"))
    assert target == set()


# ---------------------------------------------------------------------------
# _collect_flatten_candidates
# ---------------------------------------------------------------------------


def test_collect_flatten_candidates_path_field(tmp_path: Path) -> None:
    """Findings with a SPLIT verdict + an existing path produce a candidate."""
    f = tmp_path / "test_x.py"
    f.write_text("")
    findings = [{"verdict": "SPLIT", "path": str(f)}]
    assert _collect_flatten_candidates(findings) == {f}


def test_collect_flatten_candidates_files_field(tmp_path: Path) -> None:
    """Findings without ``path`` but with ``files`` add each existing entry."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("")
    b.write_text("")
    findings = [
        {"verdict": "SPLIT", "files": [str(a), str(b), str(tmp_path / "ghost.py")]}
    ]
    assert _collect_flatten_candidates(findings) == {a, b}


def test_collect_flatten_candidates_skips_non_split_verdicts(tmp_path: Path) -> None:
    """Other verdicts (RENAME, MERGE, etc.) are not flatten candidates."""
    f = tmp_path / "x.py"
    f.write_text("")
    findings = [{"verdict": "RENAME", "path": str(f)}]
    assert _collect_flatten_candidates(findings) == set()


# ---------------------------------------------------------------------------
# _is_canonical_tier
# ---------------------------------------------------------------------------


def test_is_canonical_tier_integration_and_e2e() -> None:
    """_is_canonical_tier returns True only for integration/e2e paths."""
    assert _is_canonical_tier(Path("/p/tests/integration/test_x.py")) is True
    assert _is_canonical_tier(Path("/p/tests/e2e/test_x.py")) is True
    assert _is_canonical_tier(Path("/p/tests/unit/test_x.py")) is False
    assert _is_canonical_tier(Path("/p/src/x.py")) is False


# ---------------------------------------------------------------------------
# _split_op_from_finding
# ---------------------------------------------------------------------------


def test_split_op_from_finding_uses_suggested_splits(tmp_path: Path) -> None:
    """Suggested splits are sanitised via safe_filename and produce targets."""
    src = tmp_path / "tests" / "integration" / "test_orig.py"
    src.parent.mkdir(parents=True)
    src.write_text("")
    finding = {
        "suggested_splits": ["test_a__b.py", "test_c__d.py"],
    }
    op = _split_op_from_finding(finding, src)
    assert op.kind == "split"
    assert op.source == src
    assert isinstance(op.target, list)
    target_names = {p.name for p in op.target}
    assert target_names == {"test_a__b.py", "test_c__d.py"}
    assert op.source_rule == "TEST_QUALITY_FILE_NAMING"


def test_split_op_from_finding_drops_unknown_targets(tmp_path: Path) -> None:
    """Targets named ``test_UNKNOWN.py`` are filtered out."""
    src = tmp_path / "test_orig.py"
    src.write_text("")
    finding = {
        "suggested_splits": ["test_UNKNOWN.py", "test_real.py"],
    }
    op = _split_op_from_finding(finding, src)
    assert [p.name for p in op.target] == ["test_real.py"]


def test_split_op_falls_back_to_proposed_name(tmp_path: Path) -> None:
    """Missing suggested_splits falls back to proposed_name."""
    src = tmp_path / "test_orig.py"
    src.write_text("")
    finding = {"proposed_name": "test_fallback.py"}
    op = _split_op_from_finding(finding, src)
    assert [p.name for p in op.target] == ["test_fallback.py"]


# ---------------------------------------------------------------------------
# _merge_ops_from_finding
# ---------------------------------------------------------------------------


def test_merge_ops_from_finding_uses_first_file_as_anchor(tmp_path: Path) -> None:
    """All files except the first become merge ops targeting the first."""
    f1 = tmp_path / "anchor.py"
    f2 = tmp_path / "other_a.py"
    f3 = tmp_path / "other_b.py"
    for f in (f1, f2, f3):
        f.write_text("")
    consumed: set[Path] = set()
    finding = {"canonical_name": "test_x.py", "tier": "integration"}
    ops = _merge_ops_from_finding(finding, [f1, f2, f3], consumed)
    assert len(ops) == 2
    assert all(op.target == f1 for op in ops)
    sources = {op.source for op in ops}
    assert sources == {f2, f3}
    assert consumed == {f2, f3}
    assert all("COLLIDE on test_x.py" in op.rationale for op in ops)


def test_merge_ops_from_finding_single_file_yields_no_ops(tmp_path: Path) -> None:
    """With a single file, there's nothing to merge."""
    f1 = tmp_path / "only.py"
    f1.write_text("")
    consumed: set[Path] = set()
    ops = _merge_ops_from_finding({"canonical_name": "c.py"}, [f1], consumed)
    assert ops == []
    assert consumed == set()
