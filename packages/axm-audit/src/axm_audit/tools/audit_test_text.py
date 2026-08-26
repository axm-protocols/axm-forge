"""Compact text formatter for ``audit_test`` ToolResult output."""

from __future__ import annotations

from axm_audit.core.test_runner import NonTestCauseDetail, TestCase, TestReport

__all__ = ["format_audit_test_text"]

_COV_THRESHOLD = 95.0


def _count_parts(passed: int, failed: int, errors: int, skipped: int) -> list[str]:
    """Build the count fragments, omitting zero-valued categories except passed."""
    parts: list[str] = [f"{passed} passed"]
    for label, value in (("failed", failed), ("errors", errors), ("skipped", skipped)):
        if value > 0:
            parts.append(f"{value} {label}")
    return parts


def _build_header(report: TestReport) -> str:
    """Build the one-line summary header with counts, duration, and coverage."""
    passed = getattr(report, "passed", 0) or 0
    failed = getattr(report, "failed", 0) or 0
    errors = getattr(report, "errors", 0) or 0
    skipped = getattr(report, "skipped", 0) or 0
    duration = getattr(report, "duration", 0.0) or 0.0
    coverage = getattr(report, "coverage", None)
    icon = "\u2705" if report.verdict else "\u274c"
    counts = " \u00b7 ".join(_count_parts(passed, failed, errors, skipped))
    collected = report.collected or 0
    header = f"audit_test | {icon} {counts} · {collected} collected | {duration:.1f}s"
    if report.pytest_return_code != 0:
        header += f" | pytest exit {report.pytest_return_code}"
    if coverage is not None:
        header += f" | cov {report.coverage:.1f}%"
    return header


def _build_failure_blocks(report: TestReport) -> list[str]:
    failures = getattr(report, "failures", None)
    if not failures:
        return []
    lines: list[str] = []
    for f in failures:
        loc = f"{f.file}:{f.line}" if f.file else ""
        lines.append(f"\u2717 {f.test} ({loc})")
        lines.append(f"  {f.error_type}: {f.message}")
        if f.traceback:
            for tb_line in f.traceback.splitlines():
                lines.append(f"    {tb_line}")
    return lines


def _build_coverage_section(report: TestReport) -> list[str]:
    """Return a ``cov<`` line listing files below the coverage threshold."""
    cov_by_file = getattr(report, "coverage_by_file", None)
    if cov_by_file is None:
        return []
    below = [
        (path, pct) for path, pct in sorted(cov_by_file.items()) if pct < _COV_THRESHOLD
    ]
    if not below:
        return []
    parts = [f"{name} {pct:.1f}%" for name, pct in below]
    return ["cov< " + " \u00b7 ".join(parts)]


_CASE_OUTCOME_ORDER = ("failed", "error", "xpassed", "skipped", "xfailed", "passed")


def _build_case_section(report: TestReport) -> list[str]:
    """Render opted-in per-case evidence grouped by pytest outcome."""
    if not report.cases:
        return []

    grouped: dict[str, list[TestCase]] = {}
    for case in report.cases:
        grouped.setdefault(case.outcome, []).append(case)

    ordered_outcomes = [
        outcome for outcome in _CASE_OUTCOME_ORDER if outcome in grouped
    ]
    ordered_outcomes.extend(sorted(set(grouped).difference(ordered_outcomes)))

    lines = [f"cases | {len(report.cases)}"]
    for outcome in ordered_outcomes:
        cases = grouped[outcome]
        lines.append(f"{outcome} ({len(cases)}):")
        for case in cases:
            lines.append(case.node_id)
            if case.detail:
                lines.extend(f"  {line}" for line in case.detail.splitlines())
    return lines


def _build_cause_block(report: TestReport) -> list[str]:
    """Render the classified non-test cause right under the header line.

    Strictly conditional: a report carrying no cause renders exactly as
    before, byte for byte. The excerpt is the one the classifier already
    bounded, emitted verbatim -- never truncated a second time here.
    """
    cause: NonTestCauseDetail | None = getattr(report, "non_test_cause", None)
    if cause is None:
        return []
    return [f"cause {cause.code}: {cause.summary}", *cause.excerpt.splitlines()]


def _build_target_section(report: TestReport) -> list[str]:
    """Render invalid requested targets with their validation status."""
    return [
        f"target {status['target']}: {status['status']}"
        for status in report.target_statuses
        if status["status"] != "validated"
    ]


def format_audit_test_text(report: TestReport) -> str:
    """Render a TestReport as compact text for LLM consumption."""
    lines: list[str] = [_build_header(report)]
    lines.extend(_build_cause_block(report))
    lines.extend(_build_target_section(report))
    lines.extend(_build_failure_blocks(report))
    lines.extend(_build_case_section(report))
    lines.extend(_build_coverage_section(report))
    return "\n".join(lines)
