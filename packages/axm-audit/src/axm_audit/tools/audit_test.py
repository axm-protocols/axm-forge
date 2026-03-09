"""MCP tool for agent-optimized test execution."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from axm.tools.base import AXMTool, ToolResult

__all__ = ["AuditTestTool"]


class AuditTestTool(AXMTool):
    """Run tests with agent-optimized, token-efficient output.

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
        """Run tests with agent-optimized output.

        Args:
            path: Path to project root.
            mode: Output mode (compact, failures, delta, targeted).
            files: Specific test files to run.
            markers: Pytest markers to filter.
            stop_on_first: Stop on first failure.

        Returns:
            ToolResult with structured test report.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_audit.core.test_runner import run_tests

            valid_modes: set[str] = {"compact", "failures", "delta", "targeted"}
            if mode not in valid_modes:
                return ToolResult(
                    success=False,
                    error=(
                        f"Invalid mode '{mode}'."
                        f" Must be one of: {', '.join(sorted(valid_modes))}"
                    ),
                )

            report = run_tests(
                project_path,
                mode=mode,  # type: ignore[arg-type]
                files=files,
                markers=markers,
                stop_on_first=stop_on_first,
            )

            return ToolResult(success=True, data=dataclasses.asdict(report))
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
