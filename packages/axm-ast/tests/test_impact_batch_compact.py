from __future__ import annotations

from typing import Any

from axm_ast.tools.impact import (
    ImpactTool,
    format_impact_compact,
)


def _make_report(  # noqa: PLR0913
    symbol: str,
    *,
    module: str = "mod",
    line: int = 1,
    callers: list[dict[str, Any]] | None = None,
    score: str = "LOW",
    test_files: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal per-symbol impact report dict."""
    return {
        "symbol": symbol,
        "definition": {
            "name": symbol,
            "module": module,
            "line": line,
            "type": "function",
        },
        "callers": callers or [],
        "score": score,
        "test_files": test_files or [],
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_batch_compact_preserves_per_symbol_data():
    """Each symbol must have its own row with its own callers."""
    reports = [
        _make_report(
            "func_a",
            module="pkg.alpha",
            line=10,
            callers=[{"name": "caller_x", "module": "pkg.alpha", "line": 20}],
        ),
        _make_report(
            "func_b",
            module="pkg.beta",
            line=30,
            callers=[{"name": "caller_y", "module": "pkg.beta", "line": 40}],
        ),
    ]
    result = format_impact_compact(reports)

    lines = result.strip().split("\n")
    row_a = next(row for row in lines if "func_a" in row)
    row_b = next(row for row in lines if "func_b" in row)

    # Per-symbol callers — not mixed
    assert "caller_x" in row_a
    assert "caller_y" in row_b
    assert "caller_y" not in row_a
    assert "caller_x" not in row_b


def test_batch_compact_score_max():
    """Max score (HIGH) shown on first row only, second row score is empty."""
    reports = [
        _make_report("sym_low", score="LOW"),
        _make_report("sym_high", score="HIGH"),
    ]
    result = format_impact_compact(reports)

    lines = result.strip().split("\n")
    data_rows = [
        row
        for row in lines
        if row.startswith("|") and "Symbol" not in row and "---" not in row
    ]
    assert len(data_rows) == 2
    # First row carries the max score
    assert "HIGH" in data_rows[0]
    # Second row score cell must be empty
    cols_second = [c.strip() for c in data_rows[1].split("|")]
    assert cols_second[3] == ""


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_execute_batch_compact_e2e(tmp_path):
    """ImpactTool batch+compact on a real fixture package."""
    pkg = tmp_path / "mypkg"
    src = pkg / "src" / "mypkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text(
        "def helper():\n    return 1\n\n\nclass MyClass:\n    pass\n"
    )
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )

    tool = ImpactTool()
    result = tool.execute(
        path=str(pkg),
        symbols=["helper", "MyClass"],
        detail="compact",
    )

    assert result.success
    compact = result.data["compact"]
    assert "helper" in compact
    assert "MyClass" in compact
    assert "not found" not in compact


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_batch_missing_symbol():
    """Missing symbol gets a 'not found' row; valid symbol is intact."""
    reports = [
        _make_report("valid_sym", module="pkg.mod", line=5),
        {"symbol": "nonexistent", "error": "not found"},
    ]
    result = format_impact_compact(reports)

    assert "valid_sym" in result
    assert "nonexistent" in result
    row_missing = next(
        row for row in result.strip().split("\n") if "nonexistent" in row
    )
    assert "not found" in row_missing


def test_batch_single_symbol_matches_single():
    """Batch with one symbol produces same output as single-symbol path."""
    report = _make_report(
        "solo",
        module="pkg.solo",
        line=1,
        callers=[{"name": "c1", "module": "pkg.solo", "line": 10}],
        score="MEDIUM",
    )
    batch_result = format_impact_compact([report])
    single_result = format_impact_compact(report)
    assert batch_result == single_result
