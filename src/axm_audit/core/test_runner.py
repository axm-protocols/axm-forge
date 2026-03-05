"""Agent-optimized test runner with structured output.

Wraps pytest with ``pytest-json-report`` to produce compact,
token-efficient results for AI coding agents.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from axm_audit.core.runner import run_in_project

__all__ = [
    "FailureDetail",
    "TestReport",
    "run_tests",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class FailureDetail:
    """Structured detail for a single test failure."""

    test: str
    """Full node ID, e.g. ``tests/unit/test_x.py::TestFoo::test_bar``."""

    error_type: str
    """Exception class name, e.g. ``AssertionError``."""

    message: str
    """One-line error message."""

    file: str
    """Relative file path."""

    line: int
    """Line number of the assertion / raising statement."""

    traceback: str
    """Short traceback (truncated to ``_MAX_TB_LINES``)."""


_MAX_TB_LINES = 5


@dataclass
class TestReport:
    """Compact test execution report."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    warnings: int = 0
    duration: float = 0.0
    coverage: float | None = None
    failures: list[FailureDetail] = field(default_factory=list)
    coverage_by_file: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_failures(tests: list[dict[str, Any]]) -> list[FailureDetail]:
    """Extract ``FailureDetail`` items from pytest-json-report tests list."""
    failures: list[FailureDetail] = []
    for test in tests:
        outcome = test.get("outcome", "")
        if outcome not in ("failed", "error"):
            continue

        nodeid: str = test.get("nodeid", "unknown")
        call_info: dict[str, Any] = test.get("call", {})
        crash: dict[str, Any] = call_info.get("crash", {})
        tb_text: str = call_info.get("longrepr", "")

        # Truncate traceback to _MAX_TB_LINES
        tb_lines = tb_text.strip().splitlines()
        if len(tb_lines) > _MAX_TB_LINES:
            tb_lines = tb_lines[-_MAX_TB_LINES:]
        short_tb = "\n".join(tb_lines)

        # Extract error type from the crash message
        message = crash.get("message", "")
        error_type = "Error"
        if ":" in message:
            error_type = message.split(":")[0].strip()

        failures.append(
            FailureDetail(
                test=nodeid,
                error_type=error_type,
                message=message,
                file=crash.get("path", ""),
                line=crash.get("lineno", 0),
                traceback=short_tb,
            )
        )
    return failures


def _parse_json_report(report_path: Path) -> dict[str, Any]:
    """Read and parse a pytest-json-report JSON file."""
    try:
        return json.loads(report_path.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse JSON report: %s", exc)
        return {}


def _parse_coverage(coverage_path: Path) -> tuple[float | None, dict[str, float]]:
    """Parse coverage JSON into total % and per-file dict."""
    if not coverage_path.exists():
        return None, {}
    try:
        data = json.loads(coverage_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, {}

    total_pct = data.get("totals", {}).get("percent_covered")
    per_file: dict[str, float] = {}
    for fpath, fdata in data.get("files", {}).items():
        per_file[fpath] = fdata.get("summary", {}).get("percent_covered", 0.0)

    return total_pct, per_file


def _build_pytest_cmd(
    *,
    report_path: Path,
    coverage_path: Path | None,
    files: list[str] | None,
    markers: list[str] | None,
    stop_on_first: bool,
) -> list[str]:
    """Build the pytest command line."""
    cmd = [
        "pytest",
        "--json-report",
        f"--json-report-file={report_path}",
        "--json-report-omit=collectors,log,keywords",
        "--tb=short",
        "--no-header",
        "-q",
    ]

    if coverage_path is not None:
        cmd.extend(["--cov", f"--cov-report=json:{coverage_path}"])

    if stop_on_first:
        cmd.append("-x")

    if markers:
        cmd.extend(["-m", " or ".join(markers)])

    if files:
        cmd.extend(files)

    return cmd


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

type TestMode = Literal["compact", "failures", "delta", "targeted"]


def run_tests(
    project_path: Path,
    *,
    mode: TestMode = "failures",
    files: list[str] | None = None,
    markers: list[str] | None = None,
    stop_on_first: bool = True,
    last_coverage: dict[str, float] | None = None,
) -> TestReport:
    """Run tests with agent-optimized structured output.

    Args:
        project_path: Root of the project to test.
        mode: Output mode — ``compact`` (summary only),
            ``failures`` (summary + failure details),
            ``delta`` (failures + coverage changes),
            ``targeted`` (failures for specific files/markers).
        files: Specific test files or paths to run.
        markers: Pytest markers to filter (``-m``).
        stop_on_first: Stop on first failure (``-x``).
        last_coverage: Previous per-file coverage dict for delta mode.

    Returns:
        Structured ``TestReport`` with mode-appropriate fields populated.
    """
    include_coverage = mode in ("compact", "failures", "delta")

    # Create temp files for reports
    report_tmp = tempfile.NamedTemporaryFile(
        suffix=".json", prefix="axm_report_", delete=False
    )
    report_path = Path(report_tmp.name)
    report_tmp.close()

    coverage_path: Path | None = None
    if include_coverage:
        cov_tmp = tempfile.NamedTemporaryFile(
            suffix=".json", prefix="axm_cov_", delete=False
        )
        coverage_path = Path(cov_tmp.name)
        cov_tmp.close()

    try:
        cmd = _build_pytest_cmd(
            report_path=report_path,
            coverage_path=coverage_path,
            files=files,
            markers=markers,
            stop_on_first=stop_on_first,
        )

        logger.debug("Running: %s", " ".join(cmd))
        run_in_project(
            cmd,
            project_path,
            with_packages=["pytest-json-report", "pytest-cov"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Parse JSON report
        report_data = _parse_json_report(report_path)
        summary = report_data.get("summary", {})
        tests_list: list[dict[str, Any]] = report_data.get("tests", [])

        # Parse coverage
        total_cov: float | None = None
        per_file_cov: dict[str, float] = {}
        if coverage_path is not None:
            total_cov, per_file_cov = _parse_coverage(coverage_path)

        # Build report
        result = TestReport(
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            errors=summary.get("error", 0),
            skipped=summary.get("skipped", 0),
            warnings=summary.get("warnings", 0),
            duration=report_data.get("duration", 0.0),
            coverage=total_cov,
        )

        # Populate failures for modes that need them
        if mode != "compact":
            result.failures = _parse_failures(tests_list)

        # Populate coverage delta for delta mode
        if mode == "delta" and last_coverage is not None:
            delta: dict[str, float] = {}
            all_files = set(per_file_cov) | set(last_coverage)
            for fpath in sorted(all_files):
                old = last_coverage.get(fpath, 0.0)
                new = per_file_cov.get(fpath, 0.0)
                if old != new:
                    delta[fpath] = round(new - old, 1)
            result.coverage_by_file = delta
        elif mode == "delta":
            result.coverage_by_file = per_file_cov

        return result

    finally:
        report_path.unlink(missing_ok=True)
        if coverage_path is not None:
            coverage_path.unlink(missing_ok=True)
