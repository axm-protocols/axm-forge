"""Unit tests for the code-metrics collector."""

from __future__ import annotations

from pathlib import Path

from axm_audit.code_metrics import collect_code_metrics


def test_counts_loc_under_src_skipping_blanks_and_tests(tmp_path: Path) -> None:
    """LOC counts non-blank src/**/*.py lines; tests/ and .venv/ are excluded."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    body = "import os\n\n\ndef f():\n    return 1\n"
    (src / "a.py").write_text(body, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("assert True\nassert True\n", encoding="utf-8")

    metrics = collect_code_metrics(str(tmp_path))
    assert metrics["lines"] == 3  # only src counted; blanks + tests skipped


def test_no_python_files_yields_no_lines(tmp_path: Path) -> None:
    """A path with no Python files omits the ``lines`` key, never raises."""
    metrics = collect_code_metrics(str(tmp_path))
    assert "lines" not in metrics
