"""Reporters — output formatters for Agent and Human consumption.

Provides both JSON (for AI Agents) and Markdown (for reasoning) outputs.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from axm_audit.models.results import AuditResult


class Reporter(ABC):
    """Base class for output reporters."""

    @abstractmethod
    def render(self, result: BaseModel) -> str:
        """Render a result to string output."""


class JsonReporter(Reporter):
    """Pure JSON reporter for Agent consumption.

    Outputs valid JSON with no formatting, colors, or ANSI codes.
    """

    def render(self, result: BaseModel) -> str:
        """Render result as pure JSON string."""
        return result.model_dump_json(indent=2)


class MarkdownReporter(Reporter):
    """Markdown reporter for human-readable output.

    Generates tables suitable for Agent reasoning and documentation.
    """

    def render(self, result: BaseModel) -> str:
        """Render result as Markdown table."""
        if isinstance(result, AuditResult):
            return self._render_audit(result)
        return result.model_dump_json(indent=2)

    def _render_audit(self, result: AuditResult) -> str:
        """Render AuditResult as markdown with grade."""
        parts = [
            self._render_header(result),
            self._render_grade(result),
            self._render_summary(result),
            self._render_checks(result),
            self._render_fix_hints(result),
        ]
        return "\n".join(part for part in parts if part)

    def _render_header(self, result: AuditResult) -> str:
        status_icon = "✅ PASSED" if result.success else "❌ FAILED"
        return f"# Audit Report\n\n**Status:** {status_icon}"

    def _render_grade(self, result: AuditResult) -> str:
        if result.quality_score is not None and result.grade is not None:
            return f"**Grade:** {result.grade} ({result.quality_score:.1f}/100)"
        return ""

    def _render_summary(self, result: AuditResult) -> str:
        passed_count = result.total - result.failed
        return (
            f"**Total:** {result.total} | **Passed:** {passed_count} "
            f"| **Failed:** {result.failed}\n"
        )

    def _render_checks(self, result: AuditResult) -> str:
        lines = [
            "| Rule ID | Status | Message |",
            "|---------|--------|---------|",
        ]
        for check in result.checks:
            status = "✅" if check.passed else "❌"
            lines.append(f"| {check.rule_id} | {status} | {check.message} |")
        return "\n".join(lines)

    def _render_fix_hints(self, result: AuditResult) -> str:
        failed_with_hints = [c for c in result.checks if not c.passed and c.fix_hint]
        if not failed_with_hints:
            return ""

        lines = ["", "## Fix Hints"]
        for check in failed_with_hints:
            lines.append(f"- **{check.rule_id}**: {check.fix_hint}")
        return "\n".join(lines)
