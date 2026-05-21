"""MCP tool for deterministic test-suite auto-fixing."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_audit.core.fix.models import FileOp, PipelineReport

__all__ = ["AuditFixTool"]


def _op_to_dict(op: FileOp) -> dict[str, object]:
    d = dataclasses.asdict(op)
    d["source"] = str(op.source)
    if isinstance(op.target, list):
        d["target"] = [str(t) for t in op.target]
    else:
        d["target"] = str(op.target)
    return d


def _report_to_dict(report: PipelineReport) -> dict[str, object]:
    return {
        "ops": [_op_to_dict(op) for op in report.ops],
        "unfixable": list(report.unfixable),
        "applied": report.applied,
        "warnings": list(report.warnings),
        "iterations": report.iterations,
        "by_kind": report.by_kind(),
    }


class AuditFixTool(AXMTool):
    """Run the deterministic test-suite fix pipeline.

    Registered as ``audit_fix`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "audit_fix"

    def execute(
        self,
        *,
        path: str = ".",
        apply: bool = False,
        rules: list[str] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Run the fix pipeline on a project.

        Args:
            path: Path to project root.
            apply: If True, mutate the tree; otherwise dry-run.
            rules: Optional list of rule ids to filter the pipeline.

        Returns:
            ToolResult with a JSON-serializable ``data`` dict and a
            human-readable ``text`` summary.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )

            from axm_audit.core.fix import run
            from axm_audit.core.fix.report import format_report

            rules_set = set(rules) if rules is not None else None
            report = run(project_path, apply=apply, rules=rules_set)

            data = _report_to_dict(report)
            text = format_report(report, project_path)

            return ToolResult(success=True, data=data, text=text)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=str(exc))
