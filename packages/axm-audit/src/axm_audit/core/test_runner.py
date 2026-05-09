"""Agent-optimized test runner with structured output.

Wraps pytest with ``pytest-json-report`` to produce compact,
token-efficient results for AI coding agents.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

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
    """Compact test execution report.

    All fields use ``None`` rather than empty containers when no data
    exists so that ``dataclasses.asdict`` produces a minimal payload.
    """

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    warnings: int = 0
    duration: float = 0.0
    coverage: float | None = None
    failures: list[FailureDetail] | None = None
    coverage_by_file: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def parse_failures(tests: list[dict[str, object]]) -> list[FailureDetail]:
    """Extract ``FailureDetail`` items from pytest-json-report tests list."""
    failures: list[FailureDetail] = []
    for test in tests:
        outcome = test.get("outcome", "")
        if outcome not in ("failed", "error"):
            continue

        nodeid = cast(str, test.get("nodeid", "unknown"))
        call_info = cast(
            "dict[str, object]", test.get("call") or test.get("setup") or {}
        )
        crash = cast("dict[str, object]", call_info.get("crash", {}))
        tb_text = cast(str, call_info.get("longrepr", ""))

        # Truncate traceback to _MAX_TB_LINES
        tb_lines = tb_text.strip().splitlines()
        if len(tb_lines) > _MAX_TB_LINES:
            tb_lines = tb_lines[-_MAX_TB_LINES:]
        short_tb = "\n".join(tb_lines)

        # Extract error type from the crash message
        message = cast(str, crash.get("message", ""))
        error_type = "Error"
        if ":" in message:
            error_type = message.split(":")[0].strip()

        failures.append(
            FailureDetail(
                test=nodeid,
                error_type=error_type,
                message=message,
                file=cast(str, crash.get("path", "")),
                line=cast(int, crash.get("lineno", 0)),
                traceback=short_tb,
            )
        )
    return failures


def parse_collector_errors(
    collectors: list[dict[str, object]],
) -> list[FailureDetail]:
    """Extract ``FailureDetail`` items from pytest-json-report collectors list.

    Collector errors occur before test discovery completes (e.g.
    ``SyntaxError`` in a test file, broken imports).
    """
    failures: list[FailureDetail] = []
    for collector in collectors:
        longrepr = cast(str, collector.get("longrepr", ""))
        if not longrepr:
            continue

        nodeid = cast(str, collector.get("nodeid", "unknown"))

        # Truncate traceback
        tb_lines = longrepr.strip().splitlines()
        if len(tb_lines) > _MAX_TB_LINES:
            tb_lines = tb_lines[-_MAX_TB_LINES:]
        short_tb = "\n".join(tb_lines)

        # Extract error type from last line (e.g. "SyntaxError: invalid syntax")
        last_line = longrepr.strip().splitlines()[-1] if longrepr.strip() else ""
        error_type = "CollectionError"
        message = last_line
        if ":" in last_line:
            error_type = last_line.split(":")[0].strip()
            message = last_line

        failures.append(
            FailureDetail(
                test=nodeid,
                error_type=error_type,
                message=message,
                file=nodeid if nodeid != "unknown" else "",
                line=0,
                traceback=short_tb,
            )
        )
    return failures


def parse_json_report(report_path: Path) -> dict[str, object]:
    """Read and parse a pytest-json-report JSON file."""
    try:
        return cast("dict[str, object]", json.loads(report_path.read_text()))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse JSON report: %s", exc)
        return {}


def parse_coverage(coverage_path: Path) -> tuple[float | None, dict[str, float]]:
    """Parse coverage JSON into total % and per-file dict.

    Files whose basename equals ``__main__.py`` are excluded from the
    per-file map (they typically contain only a ``python -m`` entry
    point and are not meaningfully unit-testable). The aggregate
    ``total_pct`` from pytest-cov is left untouched, in line with
    coverage.py's ``exclude_also`` convention of filtering reports
    rather than rewriting the underlying totals.
    """
    if not coverage_path.exists():
        return None, {}
    try:
        data = cast("dict[str, object]", json.loads(coverage_path.read_text()))
    except (json.JSONDecodeError, OSError):
        return None, {}

    totals = cast("dict[str, object]", data.get("totals", {}))
    total_pct = cast("float | None", totals.get("percent_covered"))
    per_file: dict[str, float] = {}
    files_map = cast("dict[str, dict[str, object]]", data.get("files", {}))
    for fpath, fdata in files_map.items():
        if Path(fpath).name == "__main__.py":
            continue
        summary = cast("dict[str, object]", fdata.get("summary", {}))
        per_file[fpath] = cast(float, summary.get("percent_covered", 0.0))

    return total_pct, per_file


def build_pytest_cmd(
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
        "--json-report-omit=log,keywords",
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


def run_tests(
    project_path: Path,
    *,
    mode: str = "failures",
    files: list[str] | None = None,
    markers: list[str] | None = None,
    stop_on_first: bool = True,
) -> TestReport:
    """Run tests with agent-optimized structured output.

    Args:
        project_path: Root of the project to test.
        mode: Accepted for backward compatibility but ignored — all modes
            now produce the same unified output (failures + coverage).
        files: Specific test files or paths to run.
        markers: Pytest markers to filter (``-m``).
        stop_on_first: Stop on first failure (``-x``).

    Returns:
        Structured ``TestReport`` with failures and coverage populated.
    """
    # Create temp files for reports
    report_tmp = tempfile.NamedTemporaryFile(
        suffix=".json", prefix="axm_report_", delete=False
    )
    report_path = Path(report_tmp.name)
    report_tmp.close()

    cov_tmp = tempfile.NamedTemporaryFile(
        suffix=".json", prefix="axm_cov_", delete=False
    )
    coverage_path = Path(cov_tmp.name)
    cov_tmp.close()

    try:
        effective_cov_path = None if files else coverage_path
        cmd = build_pytest_cmd(
            report_path=report_path,
            coverage_path=effective_cov_path,
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
        report_data = parse_json_report(report_path)

        # Parse coverage
        total_cov, per_file_cov = (
            parse_coverage(coverage_path) if not files else (None, {})
        )

        return build_test_report(
            report_data=report_data,
            total_cov=total_cov,
            per_file_cov=per_file_cov,
        )

    finally:
        report_path.unlink(missing_ok=True)
        coverage_path.unlink(missing_ok=True)


def build_test_report(
    *,
    report_data: dict[str, object],
    total_cov: float | None,
    per_file_cov: dict[str, float],
    mode: str | None = None,
    last_coverage: dict[str, float] | None = None,
) -> TestReport:
    """Build a ``TestReport`` from pytest JSON and coverage data.

    Always parses failures and populates coverage — no mode branching.
    Returns ``None`` for ``failures`` and ``coverage_by_file`` when no
    data exists.
    """
    summary = cast("dict[str, object]", report_data.get("summary", {}))
    tests_list = cast("list[dict[str, object]]", report_data.get("tests", []))

    # Always parse failures
    failures = parse_failures(tests_list)
    collectors_list = cast("list[dict[str, object]]", report_data.get("collectors", []))
    failures.extend(parse_collector_errors(collectors_list))

    return TestReport(
        passed=cast(int, summary.get("passed", 0)),
        failed=cast(int, summary.get("failed", 0)),
        errors=cast(int, summary.get("error", 0)),
        skipped=cast(int, summary.get("skipped", 0)),
        warnings=cast(int, summary.get("warnings", 0)),
        duration=cast(float, report_data.get("duration", 0.0)),
        coverage=total_cov,
        failures=failures or None,
        coverage_by_file=per_file_cov or None,
    )
