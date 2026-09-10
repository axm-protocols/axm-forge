"""InitCheckTool — project conformity check as an AXMTool."""

from __future__ import annotations

from pathlib import Path

from axm.tools.base import ToolResult

__all__ = ["InitCheckTool"]


class InitCheckTool:
    """Check a project against the AXM gold standard.

    Registered as ``init_check`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_check"

    def execute(
        self,
        path: str = ".",
        *,
        category: str | None = None,
        json_output: bool = False,
        agent: bool = False,
        verbose: bool = False,
    ) -> ToolResult:
        """Check a project against the AXM gold standard.

        Args:
            **kwargs: Keyword arguments.
                path: Path to project root.
                category: Optional category filter.

        Returns:
            ToolResult with check scores and details.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_init.core.checker import (
                CheckEngine,
                format_agent,
                format_agent_text,
                format_report,
                protocol_status,
                resolve_exit_code,
            )
            from axm_init.models.check import ProjectResult

            engine = CheckEngine(project_path, category=category)
            result = engine.run()
            data = format_agent(result)
            if category == "protocols" and isinstance(result, ProjectResult):
                data["protocols"] = protocol_status(result)

            from axm_init.quality_trace import record_quality_snapshot

            record_quality_snapshot(
                path=str(project_path), kind="governance", data=data
            )
            success = (
                resolve_exit_code(result) == 0
                if isinstance(result, ProjectResult)
                else True
            )
            if json_output or agent:
                text = None
            elif verbose and isinstance(result, ProjectResult):
                text = format_report(result, verbose=True)
            else:
                text = format_agent_text(result)
            return ToolResult(
                success=success,
                data=data,
                text=text,
                error=None if success else "Gold-standard checks failed",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
