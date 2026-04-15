from __future__ import annotations

from pathlib import PurePosixPath

from axm_audit.core.test_runner import TestReport

__all__ = ["format_audit_test_text"]

_COV_THRESHOLD = 95.0
_MAX_NODEID_LEN = 120


def _build_header(report: TestReport) -> str:
    """Build the one-line summary header with counts, duration, and coverage."""
    passed = getattr(report, "passed", 0) or 0
    failed = getattr(report, "failed", 0) or 0
    errors = getattr(report, "errors", 0) or 0
    skipped = getattr(report, "skipped", 0) or 0
    duration = getattr(report, "duration", 0.0) or 0.0
    coverage = getattr(report, "coverage", None)
    icon = "\u2705" if (failed + errors) == 0 else "\u274c"
    parts: list[str] = [f"{passed} passed"]
    if failed > 0:
        parts.append(f"{failed} failed")
    if errors > 0:
        parts.append(f"{errors} errors")
    if skipped > 0:
        parts.append(f"{skipped} skipped")
    counts = " \u00b7 ".join(parts)
    header = f"audit_test | {icon} {counts} | {duration:.1f}s"
    if coverage is not None:
        header += f" | cov {report.coverage:.1f}%"
    return header


def _build_failure_blocks(report: TestReport) -> list[str]:
    failures = getattr(report, "failures", None)
    if not failures:
        return []
    lines: list[str] = []
    for f in failures:
        short = f.test
        if len(short) > _MAX_NODEID_LEN:
            short = short[: _MAX_NODEID_LEN - 3] + "..."
        loc = f"{PurePosixPath(f.file).name}:{f.line}" if f.file else ""
        lines.append(f"\u2717 {short} ({loc})")
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
        (PurePosixPath(path).name, pct)
        for path, pct in sorted(cov_by_file.items())
        if pct < _COV_THRESHOLD
    ]
    if not below:
        return []
    parts = [f"{name} {pct:.1f}%" for name, pct in below]
    return ["cov< " + " \u00b7 ".join(parts)]


def format_audit_test_text(report: TestReport) -> str:
    """Render a TestReport as compact text for LLM consumption."""
    lines: list[str] = [_build_header(report)]
    lines.extend(_build_failure_blocks(report))
    lines.extend(_build_coverage_section(report))
    return "\n".join(lines)
