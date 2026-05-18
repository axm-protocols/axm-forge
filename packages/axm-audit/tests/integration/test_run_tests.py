"""Tests for agent-optimized test runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_audit.core.test_runner import (
    run_tests,
)

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

_FAILING_REPORT: dict[str, Any] = {
    "summary": {
        "passed": 40,
        "failed": 2,
        "error": 0,
        "skipped": 0,
        "warnings": 0,
        "duration": 8.3,
    },
    "tests": [
        {"nodeid": "tests/test_foo.py::test_ok", "outcome": "passed"},
        {
            "nodeid": "tests/test_foo.py::TestClass::test_fail",
            "outcome": "failed",
            "call": {
                "crash": {
                    "path": "tests/test_foo.py",
                    "lineno": 54,
                    "message": "AssertionError: 0 != 1",
                },
                "longrepr": "line1\nline2\nline3\nline4\nline5\nline6\nline7",
            },
        },
        {
            "nodeid": "tests/test_bar.py::test_error",
            "outcome": "error",
            "call": {
                "crash": {
                    "path": "tests/test_bar.py",
                    "lineno": 10,
                    "message": "ImportError: no module named 'foo'",
                },
                "longrepr": "short tb",
            },
        },
    ],
}

_COVERAGE_DATA: dict[str, Any] = {
    "totals": {"percent_covered": 91.5},
    "files": {
        "src/pkg/core.py": {"summary": {"percent_covered": 95.0}},
        "src/pkg/utils.py": {"summary": {"percent_covered": 80.0}},
    },
}


# ---------------------------------------------------------------------------
# run_tests — compact mode
# ---------------------------------------------------------------------------


class TestRunTestsCompact:
    @patch("axm_audit.core.test_runner.run_in_project")
    def test_all_pass(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Compact mode returns only summary fields, no failures list."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            # Write report file at the path specified in --json-report-file
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            # Write coverage file at the path in --cov-report=json:
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="compact")
        assert report.passed == 42
        assert report.failed == 0
        assert report.failures is None  # unified: no failures when all pass
        assert report.coverage == 91.5

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_with_failures(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Compact mode still has failed count but no failure details."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_FAILING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=1)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="compact")
        assert report.failed == 2
        assert report.failures is not None
        assert len(report.failures) == 2  # unified: failures always parsed


# ---------------------------------------------------------------------------
# run_tests — failures mode
# ---------------------------------------------------------------------------


class TestRunTestsFailures:
    @patch("axm_audit.core.test_runner.run_in_project")
    def test_shows_details(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Failures mode includes failure detail list."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_FAILING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=1)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="failures")
        assert report.failed == 2
        assert report.failures is not None
        assert len(report.failures) == 2
        assert report.failures[0].error_type == "AssertionError"
        assert report.failures[0].file == "tests/test_foo.py"

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_no_failures(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Failures mode with all tests passing has empty failures list."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="failures")
        assert report.passed == 42
        assert report.failures is None  # unified: no failures → None


# ---------------------------------------------------------------------------
# run_tests — delta mode
# ---------------------------------------------------------------------------


class TestCoverageByFileExposure:
    """Verify coverage_by_file is populated in compact and failures modes."""

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_compact_mode_includes_coverage_by_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Compact mode populates coverage_by_file with per-file data."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="compact")
        assert report.coverage_by_file is not None
        assert report.coverage_by_file["src/pkg/core.py"] == 95.0
        assert report.coverage_by_file["src/pkg/utils.py"] == 80.0

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_failures_mode_includes_coverage_by_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Failures mode populates coverage_by_file."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="failures")
        assert report.coverage_by_file is not None
        assert "src/pkg/core.py" in report.coverage_by_file


# ---------------------------------------------------------------------------
# run_tests — targeted mode
# ---------------------------------------------------------------------------


class TestRunTestsTargeted:
    @patch("axm_audit.core.test_runner.run_in_project")
    def test_files_passed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Targeted mode passes specific files to pytest command."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="targeted", files=["tests/test_a.py"])
        assert report.passed == 42
        # Verify the command included the file
        call_args = mock_run.call_args
        cmd_used = call_args[0][0]
        assert "tests/test_a.py" in cmd_used

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_markers_passed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Targeted mode passes markers to pytest command."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        run_tests(tmp_path, mode="targeted", markers=["not slow"])
        cmd_used = mock_run.call_args[0][0]
        assert "-m" in cmd_used
        assert "not slow" in cmd_used


# ---------------------------------------------------------------------------
# run_tests — warnings
# ---------------------------------------------------------------------------


class TestWarnings:
    @patch("axm_audit.core.test_runner.run_in_project")
    def test_warnings_captured(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Warnings count is captured in the report."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="compact")
        assert report.warnings == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @patch("axm_audit.core.test_runner.run_in_project")
    def test_no_tests_discovered(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Empty test directory returns zero counts, no error."""
        empty_report: dict[str, Any] = {
            "summary": {
                "passed": 0,
                "failed": 0,
                "error": 0,
                "skipped": 0,
                "warnings": 0,
                "duration": 0.1,
            },
            "tests": [],
        }

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(empty_report))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    pass  # Don't write coverage data — simulate missing pytest-cov
            return MagicMock(returncode=5)  # pytest exit code for no tests

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="failures")
        assert report.passed == 0
        assert report.failed == 0
        assert report.failures is None

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_no_coverage_configured(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """No pytest-cov in target project → coverage=None."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            # Don't write coverage file — simulate missing pytest-cov
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, mode="compact")
        assert report.passed == 42
        # Coverage may be None if the tmp file wasn't populated


class TestRunTestsFilesCoverage:
    """Functional tests: run_tests must skip coverage collection when files is set."""

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_run_tests_files_no_coverage(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """When files are specified, coverage must be None."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            # No coverage file written — --cov should not be in cmd
            assert "--cov" not in cmd
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, files=["tests/test_callers.py"])
        assert report.coverage is None
        assert report.coverage_by_file is None

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_run_tests_default_has_coverage(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Default invocation (no files) must collect coverage."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path)
        assert report.coverage is not None


class TestRunTestsFilesCoverageEdgeCases:
    """Edge cases for files + coverage interaction."""

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_empty_files_list_collects_coverage(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """files=[] is treated as no-files — coverage collected normally."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            for arg in cmd:
                if arg.startswith("--cov-report=json:"):
                    cpath = Path(arg.split(":", 1)[1])
                    cpath.write_text(json.dumps(_COVERAGE_DATA))
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(tmp_path, files=[])
        assert report.coverage is not None

    @patch("axm_audit.core.test_runner.run_in_project")
    def test_files_with_markers_no_coverage(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """files + markers combined — files takes precedence, no coverage."""

        def _side_effect(
            cmd: list[str], project_path: Path, **kwargs: Any
        ) -> MagicMock:
            for arg in cmd:
                if arg.startswith("--json-report-file="):
                    rpath = Path(arg.split("=", 1)[1])
                    rpath.write_text(json.dumps(_PASSING_REPORT))
            assert "--cov" not in cmd
            return MagicMock(returncode=0)

        mock_run.side_effect = _side_effect

        report = run_tests(
            tmp_path, files=["tests/test_callers.py"], markers=["not slow"]
        )
        assert report.coverage is None
        assert report.coverage_by_file is None


def test_run_tests_injects_pytest_plugins(tmp_path: Path) -> None:
    """run_tests passes with_packages=["pytest-json-report", "pytest-cov"]."""
    import json

    from axm_audit.core.test_runner import run_tests

    passing_report = {
        "summary": {
            "passed": 1,
            "failed": 0,
            "error": 0,
            "skipped": 0,
            "warnings": 0,
            "duration": 0.1,
        },
        "tests": [],
    }
    coverage_data = {
        "totals": {"percent_covered": 90.0},
        "files": {},
    }

    def _side_effect(cmd: list[str], project_path: Path, **kwargs: object) -> MagicMock:
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                Path(arg.split("=", 1)[1]).write_text(json.dumps(passing_report))
            if arg.startswith("--cov-report=json:"):
                Path(arg.split(":", 1)[1]).write_text(json.dumps(coverage_data))
        return MagicMock(returncode=0)

    with patch("axm_audit.core.test_runner.run_in_project") as mock:
        mock.side_effect = _side_effect
        run_tests(tmp_path, mode="compact")
        assert mock.call_args[1]["with_packages"] == [
            "pytest-json-report",
            "pytest-cov",
        ]


def _make_report_data(*, num_failed: int = 0, num_passed: int = 5) -> dict[str, object]:
    """Build minimal pytest JSON report data."""
    tests: list[dict[str, object]] = []
    for i in range(num_passed):
        tests.append(
            {"nodeid": f"tests/test_ex.py::test_pass_{i}", "outcome": "passed"}
        )
    for i in range(num_failed):
        tests.append(
            {
                "nodeid": f"tests/test_ex.py::test_fail_{i}",
                "outcome": "failed",
                "call": {"longrepr": f"AssertionError: {i}"},
            }
        )
    return {
        "summary": {
            "passed": num_passed,
            "failed": num_failed,
            "error": 0,
            "skipped": 0,
            "warnings": 0,
        },
        "tests": tests,
        "duration": 1.0,
    }


@pytest.mark.integration
class TestRunTestsIgnoresMode:
    """AC3: run_tests still accepts mode but ignores it."""

    def test_run_tests_ignores_mode(self, monkeypatch, tmp_path):
        report_data = _make_report_data(num_failed=1, num_passed=3)
        per_file = {"src/a.py": 75.0}

        monkeypatch.setattr(
            "axm_audit.core.test_runner.run_in_project",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_json_report",
            lambda _: report_data,
        )
        monkeypatch.setattr(
            "axm_audit.core.test_runner.parse_coverage",
            lambda _: (75.0, per_file),
        )

        report = run_tests(tmp_path, mode="compact")

        # Coverage always collected even with compact mode
        assert report.coverage == 75.0
        assert report.coverage_by_file == per_file
        # Failures always parsed (was skipped for compact before)
        assert report.failures is not None
        assert len(report.failures) == 1
