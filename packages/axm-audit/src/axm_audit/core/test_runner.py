"""Agent-optimized test runner with structured output.

Wraps pytest with ``pytest-json-report`` to produce compact,
token-efficient results for AI coding agents.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from axm_audit.core.runner import run_in_project

__all__ = [
    "FailureDetail",
    "TestCase",
    "TestOutcome",
    "TestReport",
    "run_tests",
]

logger = logging.getLogger(__name__)

# Coverage runs the full suite under instrumentation, so it is far slower
# than a bare audit subprocess. Use a generous explicit timeout (well above
# realistic full-suite duration) so a slow/contended run is never silently
# truncated into a fabricated partial coverage %. Other subprocess rules keep
# the lower ``run_in_project`` default.
_COVERAGE_RUN_TIMEOUT = 900

# Synthetic returncode set by ``run_in_project`` on ``subprocess.TimeoutExpired``.
_TIMEOUT_RETURNCODE = 124

# How much of a failed subprocess's stderr is quoted when the JSON report is
# unusable. A failed uv resolution runs to several kilobytes; the cause is in
# its opening lines, so the head is kept and the rest dropped.
_STDERR_EXCERPT_CHARS = 1200

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


type TestOutcome = Literal[
    "passed",
    "failed",
    "error",
    "skipped",
    "xfailed",
    "xpassed",
]


@dataclass(frozen=True, slots=True)
class TestCase:
    """Lossless verdict for one collected pytest item."""

    node_id: str
    outcome: TestOutcome
    detail: str | None = field(default=None, compare=False)


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
    cases: tuple[TestCase, ...] = ()
    timed_out: bool = False
    pytest_return_code: int = 0
    collected: int | None = None
    target_statuses: list[dict[str, str]] = field(default_factory=list)
    verdict: bool | None = None

    def __post_init__(self) -> None:
        """Populate additive execution metadata for directly-built reports."""
        if self.collected is None:
            self.collected = self.passed + self.failed + self.errors + self.skipped
        if self.verdict is None:
            self.verdict = self._derive_verdict()

    def record_execution(
        self,
        *,
        return_code: int,
        collected: int,
        target_statuses: list[dict[str, str]],
    ) -> None:
        """Attach pytest evidence and compute the report's canonical verdict."""
        self.pytest_return_code = return_code
        self.collected = collected
        self.target_statuses = target_statuses
        self.verdict = self._derive_verdict()

    def _derive_verdict(self) -> bool:
        """Return the fail-closed verdict from all available evidence."""
        targets_valid = all(
            status["status"] == "validated" for status in self.target_statuses
        )
        return (
            self.pytest_return_code == 0
            and (self.collected or 0) > 0
            and self.failed == 0
            and self.errors == 0
            and not self.timed_out
            and targets_valid
        )


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


def _subprocess_failure(
    exc: ValueError,
    result: subprocess.CompletedProcess[str],
) -> ValueError:
    """Enrich an unusable-report error with the subprocess's own diagnostic.

    Returns *exc* untouched when the run exited cleanly — a zero exit with an
    unreadable report is a genuine report defect, and the subprocess has nothing
    to add. Otherwise the returncode and the head of ``stderr`` are prepended,
    since that is where the actual cause lives. The stderr is truncated to
    :data:`_STDERR_EXCERPT_CHARS`: a failed dependency resolution runs to
    several kilobytes and must not be dumped whole into an exception message.
    """
    if result.returncode == 0:
        return exc
    stderr = (result.stderr or "").strip()
    if len(stderr) > _STDERR_EXCERPT_CHARS:
        stderr = stderr[:_STDERR_EXCERPT_CHARS] + "\n[... stderr truncated]"
    detail = f"\nsubprocess stderr:\n{stderr}" if stderr else ""
    return ValueError(
        f"pytest exited with code {result.returncode} and left no usable JSON "
        f"report ({exc}).{detail}"
    )


def parse_json_report(report_path: Path) -> dict[str, object]:
    """Read and parse a pytest-json-report JSON file."""
    try:
        raw_report = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        msg = f"Invalid pytest JSON report at {report_path}: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(raw_report, dict):
        msg = f"Invalid pytest JSON report at {report_path}: root is not an object"
        raise ValueError(msg)
    if not isinstance(raw_report.get("summary"), dict):
        msg = f"Invalid pytest JSON report at {report_path}: missing object 'summary'"
        raise ValueError(msg)
    return cast("dict[str, object]", raw_report)


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


def _collected_count(report_data: dict[str, object]) -> int:
    """Read pytest's collected count, falling back to emitted test records."""
    summary = cast("dict[str, object]", report_data.get("summary", {}))
    collected = summary.get("collected")
    if isinstance(collected, int):
        return collected
    tests = cast("list[dict[str, object]]", report_data.get("tests", []))
    return len(tests)


def _normalize_target(project_path: Path, target: str) -> str:
    """Normalize a requested pytest target for comparison with node IDs."""
    path_text, separator, selector = target.partition("::")
    candidate = Path(path_text)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(project_path)
        except ValueError:
            pass
    normalized = candidate.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return f"{normalized}{separator}{selector}"


def _target_was_collected(target: str, nodeids: list[str]) -> bool:
    """Return whether pytest emitted a node belonging to the target."""
    if "::" in target:
        return any(
            nodeid == target
            or nodeid.startswith(f"{target}[")
            or nodeid.startswith(f"{target}::")
            for nodeid in nodeids
        )
    prefix = target.rstrip("/")
    return any(
        nodeid == prefix
        or nodeid.startswith(f"{prefix}::")
        or nodeid.startswith(f"{prefix}/")
        for nodeid in nodeids
    )


def _build_target_statuses(
    project_path: Path,
    files: list[str] | None,
    report_data: dict[str, object],
) -> list[dict[str, str]]:
    """Validate every requested target independently of aggregate counts."""
    if not files:
        return []
    tests = cast("list[dict[str, object]]", report_data.get("tests", []))
    nodeids = [cast(str, test.get("nodeid", "")).replace("\\", "/") for test in tests]
    statuses: list[dict[str, str]] = []
    for target in files:
        normalized = _normalize_target(project_path, target)
        if _target_was_collected(normalized, nodeids):
            status = "validated"
        else:
            path_text = target.partition("::")[0]
            target_path = Path(path_text)
            if not target_path.is_absolute():
                target_path = project_path / target_path
            status = "omitted" if target_path.exists() else "missing"
        statuses.append({"target": target, "status": status})
    return statuses


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
    include_cases: bool = False,
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
        result = run_in_project(
            cmd,
            project_path,
            timeout=_COVERAGE_RUN_TIMEOUT,
            with_packages=["pytest-json-report", "pytest-cov"],
            capture_output=True,
            text=True,
            check=False,
        )

        # A timed-out subprocess (synthetic returncode 124) leaves the
        # report/coverage JSON truncated. Surface the timeout explicitly
        # instead of parsing a fabricated coverage % from partial data.
        if result.returncode == _TIMEOUT_RETURNCODE:
            logger.warning(
                "Test run timed out after %ds — coverage not measured",
                _COVERAGE_RUN_TIMEOUT,
            )
            if include_cases:
                raise ValueError(
                    f"pytest subprocess timed out after {_COVERAGE_RUN_TIMEOUT}s"
                )
            return TestReport(
                timed_out=True,
                pytest_return_code=result.returncode,
                collected=0,
                verdict=False,
            )

        # Parse JSON report. A subprocess that died before pytest could write
        # the report (failed uv resolution, missing plugin, collection crash)
        # leaves it absent or empty: the bare JSON decode error then describes a
        # corrupt file and hides the real cause, which only the captured stderr
        # carries. Re-raise it enriched instead.
        try:
            report_data = parse_json_report(report_path)
        except ValueError as exc:
            raise _subprocess_failure(exc, result) from exc

        # Parse coverage
        total_cov, per_file_cov = (
            parse_coverage(coverage_path) if not files else (None, {})
        )

        report = build_test_report(
            report_data=report_data,
            total_cov=total_cov,
            per_file_cov=per_file_cov,
            include_cases=include_cases,
        )
        report.record_execution(
            return_code=result.returncode,
            collected=_collected_count(report_data),
            target_statuses=_build_target_statuses(
                project_path,
                files,
                report_data,
            ),
        )
        return report

    finally:
        report_path.unlink(missing_ok=True)
        coverage_path.unlink(missing_ok=True)


def _nonempty_text(value: object) -> str | None:
    """Return non-blank text from a dynamic report field."""
    return value if isinstance(value, str) and value.strip() else None


def _phase_detail(value: object) -> str | None:
    """Extract the best diagnostic from one pytest execution phase."""
    if not isinstance(value, dict):
        return None
    phase = cast("dict[str, object]", value)
    crash = phase.get("crash")
    if isinstance(crash, dict):
        crash_data = cast("dict[str, object]", crash)
        message = _nonempty_text(crash_data.get("message"))
        if message is not None:
            return message
    return _nonempty_text(phase.get("longrepr"))


def _case_detail(
    entry: dict[str, object],
    outcome: TestOutcome,
) -> str | None:
    """Extract an optional diagnostic without changing case identity."""
    if outcome == "passed":
        return None

    for phase_name in ("call", "setup", "teardown"):
        detail = _phase_detail(entry.get(phase_name))
        if detail is not None:
            return detail
    return _nonempty_text(entry.get("longrepr"))


def _extract_cases(report_data: dict[str, object]) -> tuple[TestCase, ...]:
    """Extract validated cases from a pytest-json-report payload."""
    raw_tests = report_data.get("tests")
    if not isinstance(raw_tests, list):
        raise ValueError("Malformed pytest JSON report: 'tests' must be a list")

    cases: list[TestCase] = []
    seen_node_ids: set[str] = set()
    canonical_outcomes = {
        "passed",
        "failed",
        "error",
        "skipped",
        "xfailed",
        "xpassed",
    }
    for raw_entry in raw_tests:
        if not isinstance(raw_entry, dict):
            raise ValueError("Malformed pytest JSON report: invalid tests entry")
        entry = cast("dict[str, object]", raw_entry)
        node_id = entry.get("nodeid")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("Malformed pytest JSON report: invalid node id")
        if node_id in seen_node_ids:
            raise ValueError(f"Duplicate pytest node id: {node_id}")
        seen_node_ids.add(node_id)

        raw_outcome = entry.get("outcome")
        if not isinstance(raw_outcome, str) or raw_outcome not in canonical_outcomes:
            raise ValueError(f"Unknown pytest outcome: {raw_outcome!r}")
        outcome = cast("TestOutcome", raw_outcome)
        cases.append(
            TestCase(
                node_id=node_id,
                outcome=outcome,
                detail=_case_detail(entry, outcome),
            )
        )

    return tuple(sorted(cases, key=lambda case: case.node_id))


def _collection_failure_detail(
    collectors: list[dict[str, object]],
) -> str | None:
    """Return a diagnostic when pytest failed during collection."""
    for collector in collectors:
        outcome = collector.get("outcome")
        longrepr = collector.get("longrepr")
        if outcome not in {"failed", "error"} and not longrepr:
            continue
        node_id = collector.get("nodeid")
        location = node_id if isinstance(node_id, str) else "<unknown>"
        if isinstance(longrepr, str) and longrepr.strip():
            return f"pytest collection failed for {location}: {longrepr}"
        return f"pytest collection failed for {location}"
    return None


def build_test_report(
    *,
    report_data: dict[str, object],
    total_cov: float | None,
    per_file_cov: dict[str, float],
    mode: str | None = None,
    last_coverage: dict[str, float] | None = None,
    include_cases: bool = False,
) -> TestReport:
    """Build a ``TestReport`` from pytest JSON and coverage data.

    Always parses failures and populates coverage — no mode branching.
    Returns ``None`` for ``failures`` and ``coverage_by_file`` when no
    data exists.
    """
    summary = cast("dict[str, object]", report_data.get("summary", {}))
    tests_list = cast("list[dict[str, object]]", report_data.get("tests", []))
    cases = _extract_cases(report_data) if include_cases else ()

    # Always parse failures
    failures = parse_failures(tests_list)
    collectors_list = cast("list[dict[str, object]]", report_data.get("collectors", []))
    failures.extend(parse_collector_errors(collectors_list))
    if include_cases:
        collection_failure = _collection_failure_detail(collectors_list)
        if collection_failure is not None:
            raise ValueError(collection_failure)

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
        cases=cases,
    )
