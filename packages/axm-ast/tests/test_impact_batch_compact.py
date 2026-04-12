from __future__ import annotations

from axm_ast.tools.impact import (
    format_impact_compact_multi,
)


def _make_report(
    symbol: str,
    score: str | None = None,
    *,
    module: str = "mod",
    line: int = 1,
    callers: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "symbol": symbol,
        "definition": {"module": module, "line": line, "file": f"{module}.py"},
        "callers": callers or [],
        "test_files": [],
    }
    if score is not None:
        report["score"] = score
    return report


# --- Unit tests ---


def test_batch_compact_per_symbol_scores() -> None:
    """3 reports with HIGH, LOW, MEDIUM - each row shows its own score."""
    reports = [
        _make_report("func_a", "HIGH"),
        _make_report("func_b", "LOW"),
        _make_report("func_c", "MEDIUM"),
    ]
    result = format_impact_compact_multi(reports, score="HIGH")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 3
    assert "HIGH" in rows[0]
    assert "LOW" in rows[1]
    assert "MEDIUM" in rows[2]


def test_batch_compact_all_same_score() -> None:
    """2 reports both LOW - both rows show LOW."""
    reports = [
        _make_report("alpha", "LOW"),
        _make_report("beta", "LOW"),
    ]
    result = format_impact_compact_multi(reports, score="LOW")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 2
    for row in rows:
        assert "LOW" in row


# --- Edge cases ---


def test_batch_compact_missing_score_defaults_to_low() -> None:
    """Report with no 'score' key should display LOW as default."""
    reports = [
        _make_report("no_score_sym"),
    ]
    result = format_impact_compact_multi(reports, score="LOW")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 1
    assert "LOW" in rows[0]


def test_batch_compact_single_symbol() -> None:
    """Single-symbol batch shows its own score in the row."""
    reports = [
        _make_report("only_one", "MEDIUM"),
    ]
    result = format_impact_compact_multi(reports, score="MEDIUM")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 1
    assert "MEDIUM" in rows[0]
