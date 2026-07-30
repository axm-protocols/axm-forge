"""Split from ``test_pytest_invocation_and_parsing.py``."""

import json
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.test_runner import parse_coverage

_COVERAGE_DATA: dict[str, Any] = {
    "totals": {"percent_covered": 91.5},
    "files": {
        "src/pkg/core.py": {"summary": {"percent_covered": 95.0}},
        "src/pkg/utils.py": {"summary": {"percent_covered": 80.0}},
    },
}


class TestParseCoverage:
    def test_valid_coverage(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "cov.json"
        cov_file.write_text(json.dumps(_COVERAGE_DATA))
        total, per_file = parse_coverage(cov_file)
        assert total == 91.5
        assert per_file["src/pkg/core.py"] == 95.0

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(None, id="missing_file"),
            pytest.param("bad", id="invalid_json"),
        ],
    )
    def test_degraded_input_returns_none_total(
        self, tmp_path: Path, content: str | None
    ) -> None:
        """Missing file or invalid JSON both yield (None, {})."""
        cov_file = tmp_path / "cov.json"
        if content is not None:
            cov_file.write_text(content)
        total, per_file = parse_coverage(cov_file)
        assert total is None
        assert per_file == {}


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
