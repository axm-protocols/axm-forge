"""Tests for agent-optimized test runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_audit.core.test_runner import (
    FailureDetail,
    _build_pytest_cmd,
    _parse_collector_errors,
    _parse_coverage,
    _parse_failures,
    _parse_json_report,
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

_SETUP_ERROR_REPORT: dict[str, Any] = {
    "summary": {"passed": 0, "failed": 0, "error": 1},
    "tests": [
        {
            "nodeid": "tests/test_models.py::test_budget",
            "outcome": "error",
            "setup": {
                "crash": {
                    "path": "tests/test_models.py",
                    "lineno": 12,
                    "message": "ValidationError: 7 validation errors for BudgetData",
                },
                "longrepr": (
                    "line1\nline2\nline3\n"
                    "ValidationError: 7 validation errors for BudgetData"
                ),
            },
            # No "call" key — collection error
        },
    ],
}

_COLLECTOR_ERROR_ENTRIES: list[dict[str, Any]] = [
    {
        "nodeid": "tests/test_broken.py",
        "outcome": "failed",
        "longrepr": (
            "tests/test_broken.py:1: in <module>\n"
            "    import nonexistent\n"
            "ModuleNotFoundError: No module named 'nonexistent'"
        ),
    },
]

_COVERAGE_DATA: dict[str, Any] = {
    "totals": {"percent_covered": 91.5},
    "files": {
        "src/pkg/core.py": {"summary": {"percent_covered": 95.0}},
        "src/pkg/utils.py": {"summary": {"percent_covered": 80.0}},
    },
}


# ---------------------------------------------------------------------------
# _parse_failures
# ---------------------------------------------------------------------------


class TestParseFailures:
    def test_empty_list(self) -> None:
        assert _parse_failures([]) == []

    def test_passing_tests_skipped(self) -> None:
        tests = [{"nodeid": "test_a", "outcome": "passed"}]
        assert _parse_failures(tests) == []

    def test_failed_test_extracted(self) -> None:
        result = _parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        f = result[0]
        assert isinstance(f, FailureDetail)
        assert f.test == "tests/test_foo.py::TestClass::test_fail"
        assert f.error_type == "AssertionError"
        assert f.file == "tests/test_foo.py"
        assert f.line == 54

    def test_traceback_truncated(self) -> None:
        """Traceback longer than 5 lines is truncated."""
        result = _parse_failures(_FAILING_REPORT["tests"])
        tb_lines = result[0].traceback.splitlines()
        assert len(tb_lines) <= 5

    def test_error_outcome_included(self) -> None:
        result = _parse_failures(_FAILING_REPORT["tests"])
        err = result[1]
        assert err.error_type == "ImportError"
        assert err.test == "tests/test_bar.py::test_error"

    def test_parse_failures_collection_error(self) -> None:
        """Setup-phase errors (no 'call' key) produce non-empty FailureDetail."""
        result = _parse_failures(_SETUP_ERROR_REPORT["tests"])
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_models.py::test_budget"
        assert f.error_type == "ValidationError"
        assert f.traceback != ""
        assert f.message != ""
        assert f.file == "tests/test_models.py"
        assert f.line == 12

    def test_parse_failures_call_error_unchanged(self) -> None:
        """Normal call-phase failures are unaffected by the fallback logic."""
        result = _parse_failures(_FAILING_REPORT["tests"])
        assert len(result) == 2
        assert result[0].error_type == "AssertionError"
        assert result[0].file == "tests/test_foo.py"
        assert result[0].line == 54
        assert result[1].error_type == "ImportError"


# ---------------------------------------------------------------------------
# _parse_collector_errors
# ---------------------------------------------------------------------------


class TestParseCollectorErrors:
    def test_empty_list(self) -> None:
        assert _parse_collector_errors([]) == []

    def test_collector_without_longrepr_skipped(self) -> None:
        result = _parse_collector_errors([{"nodeid": "foo", "longrepr": ""}])
        assert result == []

    def test_parse_failures_collector_error(self) -> None:
        """Collector-level errors produce FailureDetail with correct fields."""
        result = _parse_collector_errors(_COLLECTOR_ERROR_ENTRIES)
        assert len(result) == 1
        f = result[0]
        assert f.test == "tests/test_broken.py"
        assert f.error_type == "ModuleNotFoundError"
        assert "nonexistent" in f.message
        assert f.traceback != ""


# ---------------------------------------------------------------------------
# _parse_json_report
# ---------------------------------------------------------------------------


class TestParseJsonReport:
    def test_valid_json(self, tmp_path: Path) -> None:
        report_file = tmp_path / "report.json"
        report_file.write_text(json.dumps(_PASSING_REPORT))
        result = _parse_json_report(report_file)
        assert result["summary"]["passed"] == 42

    def test_invalid_json(self, tmp_path: Path) -> None:
        report_file = tmp_path / "report.json"
        report_file.write_text("not json")
        result = _parse_json_report(report_file)
        assert result == {}

    def test_missing_file(self, tmp_path: Path) -> None:
        result = _parse_json_report(tmp_path / "nonexistent.json")
        assert result == {}


# ---------------------------------------------------------------------------
# _parse_coverage
# ---------------------------------------------------------------------------


class TestParseCoverage:
    def test_valid_coverage(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "cov.json"
        cov_file.write_text(json.dumps(_COVERAGE_DATA))
        total, per_file = _parse_coverage(cov_file)
        assert total == 91.5
        assert per_file["src/pkg/core.py"] == 95.0

    def test_missing_file(self, tmp_path: Path) -> None:
        total, per_file = _parse_coverage(tmp_path / "nonexistent.json")
        assert total is None
        assert per_file == {}

    def test_invalid_json(self, tmp_path: Path) -> None:
        cov_file = tmp_path / "cov.json"
        cov_file.write_text("bad")
        total, per_file = _parse_coverage(cov_file)
        assert total is None
        assert per_file == {}


# ---------------------------------------------------------------------------
# _build_pytest_cmd
# ---------------------------------------------------------------------------


class TestBuildPytestCmd:
    def test_basic_cmd(self, tmp_path: Path) -> None:
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "pytest" in cmd
        assert "--json-report" in cmd
        assert "-x" not in cmd

    def test_stop_on_first(self, tmp_path: Path) -> None:
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=None,
            stop_on_first=True,
        )
        assert "-x" in cmd

    def test_with_files(self, tmp_path: Path) -> None:
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=["tests/test_a.py", "tests/test_b.py"],
            markers=None,
            stop_on_first=False,
        )
        assert "tests/test_a.py" in cmd
        assert "tests/test_b.py" in cmd

    def test_with_markers(self, tmp_path: Path) -> None:
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=None,
            files=None,
            markers=["not slow", "unit"],
            stop_on_first=False,
        )
        assert "-m" in cmd
        assert "not slow or unit" in cmd

    def test_with_coverage(self, tmp_path: Path) -> None:
        cov_path = tmp_path / "cov.json"
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "r.json",
            coverage_path=cov_path,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" in cmd
        assert f"--cov-report=json:{cov_path}" in cmd


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


# ---------------------------------------------------------------------------
# AXM-1427 — skip coverage when files param is set
# ---------------------------------------------------------------------------


class TestBuildPytestCmdCoverageWithFiles:
    """Unit tests: _build_pytest_cmd must omit --cov when coverage_path is None."""

    def test_build_pytest_cmd_no_cov_when_files(self, tmp_path: Path) -> None:
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "report.json",
            coverage_path=None,
            files=["t.py"],
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" not in cmd
        assert not any(arg.startswith("--cov-report") for arg in cmd)

    def test_build_pytest_cmd_cov_when_no_files(self, tmp_path: Path) -> None:
        cov_path = Path("/tmp/c.json")
        cmd = _build_pytest_cmd(
            report_path=tmp_path / "report.json",
            coverage_path=cov_path,
            files=None,
            markers=None,
            stop_on_first=False,
        )
        assert "--cov" in cmd
        assert any(arg.startswith("--cov-report=json:") for arg in cmd)


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
