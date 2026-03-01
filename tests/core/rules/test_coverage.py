"""Tests for TestCoverageRule (pytest-cov integration)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from axm_audit.models.results import CheckResult


class TestTestCoverageRule:
    """Tests for TestCoverageRule."""

    def _make_mock_result(self, stdout: str = "", returncode: int = 0) -> object:
        """Create a mock subprocess result."""
        return type(
            "Result", (), {"stdout": stdout, "stderr": "", "returncode": returncode}
        )()

    def _run_with_coverage(
        self,
        tmp_path: Path,
        coverage_data: dict[str, Any] | None = None,
        stdout: str = "",
    ) -> CheckResult:
        """Run TestCoverageRule with mocked subprocess and optional coverage data.

        When *coverage_data* is provided, the mock ``subprocess.run`` side-
        effect writes the JSON to the temp file that the rule creates,
        simulating what ``pytest-cov`` does in production.
        """
        from axm_audit.core.rules.coverage import TestCoverageRule

        mock_result = self._make_mock_result(stdout=stdout)

        def _mock_run(cmd: list[str], **kwargs: object) -> object:
            """Mock subprocess that writes coverage data to the temp file."""
            if coverage_data is not None:
                # Find the --cov-report=json:<path> argument
                for arg in cmd:
                    if arg.startswith("--cov-report=json:"):
                        cov_path = Path(arg.split(":", 1)[1])
                        cov_path.write_text(json.dumps(coverage_data))
                        break
            return mock_result

        rule = TestCoverageRule()
        with patch("subprocess.run", side_effect=_mock_run):
            return rule.check(tmp_path)

    def test_good_coverage_passes(self, tmp_path: Path) -> None:
        """90% coverage → score=90, passed=True."""
        result = self._run_with_coverage(
            tmp_path, coverage_data={"totals": {"percent_covered": 90.0}}
        )
        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 90

    def test_low_coverage_fails(self, tmp_path: Path) -> None:
        """50% coverage → score=50, passed=False."""
        result = self._run_with_coverage(
            tmp_path, coverage_data={"totals": {"percent_covered": 50.0}}
        )
        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 50

    def test_no_coverage_file(self, tmp_path: Path) -> None:
        """No coverage data written → score=0, passed=False."""
        result = self._run_with_coverage(tmp_path, coverage_data=None)
        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 0

    def test_rule_id(self) -> None:
        """Rule ID should be QUALITY_COVERAGE."""
        from axm_audit.core.rules.coverage import TestCoverageRule

        assert TestCoverageRule().rule_id == "QUALITY_COVERAGE"

    def test_coverage_rule_no_leftover_files(self, tmp_path: Path) -> None:
        """After check(), no coverage.json should remain in the project root."""
        self._run_with_coverage(
            tmp_path, coverage_data={"totals": {"percent_covered": 95.0}}
        )
        assert not (tmp_path / "coverage.json").exists()

    def test_coverage_json_preexisting_not_affected(self, tmp_path: Path) -> None:
        """Stale coverage.json in project root should not be touched."""
        stale = tmp_path / "coverage.json"
        stale.write_text('{"stale": true}')

        self._run_with_coverage(
            tmp_path, coverage_data={"totals": {"percent_covered": 95.0}}
        )
        # Stale file should still exist — rule uses its own temp file
        assert stale.exists()
        assert json.loads(stale.read_text()) == {"stale": True}
