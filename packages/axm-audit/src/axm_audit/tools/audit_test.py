"""MCP tool for structured test execution."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from axm.tools.base import AXMTool, ToolResult

if TYPE_CHECKING:
    from axm_audit.core.test_runner import TestReport

__all__ = ["AuditTestTool"]

logger = logging.getLogger(__name__)


def _tool_succeeded(report: TestReport) -> bool:
    """Whether the tool did its job, independent of the test verdict.

    ``success`` answers "did audit_test run a genuine test session?", not "did
    the tests pass" — that is ``data["verdict"]``. A red run is a successful
    measurement of a failure, so it is ``success=True``. What is *not* a
    successful measurement is the tool being unable to validate what was asked:
    a target that collected nothing, a missing/omitted target, a collection or
    usage error, a timeout. Those keep ``success=False`` so a caller can still
    tell a real tool failure from failing tests.
    """
    if report.non_test_cause is not None or report.timed_out:
        return False
    # pytest exit 0 (all passed) and 1 (tests failed) are the only codes that
    # mean "a verdict was reached"; 2 (collection/usage), 3 (internal error),
    # 4 (usage), 5 (no tests) are the tool failing to run a session.
    if report.pytest_return_code not in (0, 1):
        return False
    if (report.collected or 0) == 0:
        return False
    return all(status["status"] == "validated" for status in report.target_statuses)


class AuditTestTool(AXMTool):
    """Run tests with structured output.

    Registered as ``audit_test`` via axm.tools entry point.
    """

    expose_directly = True
    domain = "audit"
    tags = frozenset({"test", "pytest", "coverage"})

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "audit_test"

    def execute(  # noqa: PLR0913
        self,
        *,
        path: str = ".",
        mode: str = "failures",
        files: list[str] | None = None,
        markers: list[str] | None = None,
        stop_on_first: bool = True,
        include_cases: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Run tests with structured output.

        Args:
            path: Path to project root.
            mode: ``"cases"`` requests lossless per-item evidence through the
                historical field; other values remain backward-compatible.
            files: Specific test files to run.
            markers: Pytest markers to filter.
            stop_on_first: Stop on first failure.
            include_cases: Include lossless per-item pytest verdicts.

        Returns:
            ToolResult with structured test report.
        """
        include_case_evidence = include_cases or mode == "cases"
        if mode not in {"failures", "cases"}:
            logger.info("mode param is deprecated")

        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_audit.core.test_runner import run_tests

            report = run_tests(
                project_path,
                files=files,
                markers=markers,
                stop_on_first=stop_on_first,
                include_cases=include_case_evidence,
            )

            data = dataclasses.asdict(report)
            if include_case_evidence:
                data["cases"] = [dataclasses.asdict(case) for case in report.cases]
            else:
                data.pop("cases", None)

            from axm_audit.tools.audit_test_text import format_audit_test_text

            text = format_audit_test_text(report)

            return ToolResult(success=_tool_succeeded(report), data=data, text=text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
