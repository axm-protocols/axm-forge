"""Split from ``test_pytest_invocation_and_parsing.py``."""

import json
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.test_runner import parse_json_report

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PASSING_REPORT: dict[str, Any] = {
    "summary": {
        "passed": 42,
        "failed": 0,
        "error": 0,
        "skipped": 3,
        "warnings": 1,
        "duration": 12.5,
    },
    "tests": [
        {"nodeid": "tests/test_foo.py::test_bar", "outcome": "passed"},
    ],
}


class TestParseJsonReport:
    def test_valid_json(self, tmp_path: Path) -> None:
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(_PASSING_REPORT))
        result = parse_json_report(report_file)
        assert result["summary"]["passed"] == 42

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("not json", id="invalid_json"),
            pytest.param(None, id="missing_file"),
        ],
    )
    def test_degraded_input_returns_empty_dict(
        self, tmp_path: Path, content: str | None
    ) -> None:
        """Invalid JSON or missing file both return an empty dict."""
        report_file = tmp_path / "report.json"
        if content is not None:
            report_file.write_text(content)
        assert parse_json_report(report_file) == {}
