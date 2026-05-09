"""Unit tests for parse_coverage __main__.py exclusion (AXM-1663)."""

from __future__ import annotations

import json
from pathlib import Path

from axm_audit.core.test_runner import parse_coverage


def _write_coverage(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "coverage.json"
    p.write_text(json.dumps(payload))
    return p


def test_parse_coverage_excludes_main_module(tmp_path: Path) -> None:
    payload = {
        "totals": {"percent_covered": 50.0},
        "files": {
            "pkg/foo.py": {"summary": {"percent_covered": 80.0}},
            "pkg/__main__.py": {"summary": {"percent_covered": 0.0}},
            "pkg/sub/__main__.py": {"summary": {"percent_covered": 0.0}},
        },
    }
    coverage_path = _write_coverage(tmp_path, payload)

    _, per_file = parse_coverage(coverage_path)

    assert "pkg/foo.py" in per_file
    assert "pkg/__main__.py" not in per_file
    assert "pkg/sub/__main__.py" not in per_file


def test_parse_coverage_keeps_total_pct_unchanged(tmp_path: Path) -> None:
    payload = {
        "totals": {"percent_covered": 73.5},
        "files": {
            "pkg/foo.py": {"summary": {"percent_covered": 90.0}},
            "pkg/__main__.py": {"summary": {"percent_covered": 0.0}},
        },
    }
    coverage_path = _write_coverage(tmp_path, payload)

    total_pct, _ = parse_coverage(coverage_path)

    assert total_pct == 73.5


def test_parse_coverage_keeps_main_substring_files(tmp_path: Path) -> None:
    payload = {
        "totals": {"percent_covered": 100.0},
        "files": {
            "pkg/main.py": {"summary": {"percent_covered": 100.0}},
            "pkg/__main_helper.py": {"summary": {"percent_covered": 100.0}},
        },
    }
    coverage_path = _write_coverage(tmp_path, payload)

    _, per_file = parse_coverage(coverage_path)

    assert "pkg/main.py" in per_file
    assert "pkg/__main_helper.py" in per_file
