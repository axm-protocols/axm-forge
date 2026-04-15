"""MCP tool for structured test execution."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["AuditTestTool"]

logger = logging.getLogger(__name__)


class AuditTestTool(AXMTool):
    """Run tests with structured output.

    Registered as ``audit_test`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "audit_test"

    def execute(
        self,
        *,
        path: str = ".",
        mode: str = "failures",
        files: list[str] | None = None,
        markers: list[str] | None = None,
        stop_on_first: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        """Run tests with structured output.

        Args:
            path: Path to project root.
            mode: Deprecated, ignored. Kept for backward compatibility.
            files: Specific test files to run.
            markers: Pytest markers to filter.
            stop_on_first: Stop on first failure.

        Returns:
            ToolResult with structured test report.
        """
        if mode != "failures":
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
            )

            data = dataclasses.asdict(report)

            from axm_audit.tools.audit_test_text import format_audit_test_text

            text = format_audit_test_text(report)

            return ToolResult(success=True, data=data, text=text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
