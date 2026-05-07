"""Unit tests for axm_ast.tools.impact_text rendering helpers."""

from __future__ import annotations

from axm_ast.tools.impact_text import (
    render_impact_batch_text,
    render_impact_text,
)


def test_render_impact_text_renders_high_score() -> None:
    """AC1: render_impact_text emits the score and the symbol name."""
    report = {
        "symbol": "my_func",
        "score": "HIGH",
        "definition": {"module": "pkg.mod", "line": 10, "kind": "function"},
        "callers": [
            {"symbol": f"caller_{i}", "module": "pkg.other", "line": i}
            for i in range(6)
        ],
        "reexports": [{"module": f"pkg.reexport_{i}", "line": i} for i in range(3)],
        "tests": [],
        "git_coupled": [],
        "cross_package": [],
    }

    output = render_impact_text(report)

    assert "HIGH" in output
    assert "my_func" in output


def test_render_impact_batch_text_handles_multi_symbol() -> None:
    """AC1: batch render produces one section per symbol."""
    reports = [
        {
            "symbol": f"sym_{i}",
            "score": score,
            "definition": {"module": "pkg.mod", "line": i, "kind": "function"},
            "callers": [],
            "reexports": [],
            "tests": [],
            "git_coupled": [],
            "cross_package": [],
        }
        for i, score in enumerate(["LOW", "MEDIUM", "HIGH"])
    ]

    output = render_impact_batch_text(reports)

    for i in range(3):
        assert f"sym_{i}" in output
    assert output.count("## ") == 3
