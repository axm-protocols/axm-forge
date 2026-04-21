"""Quality-check hook for protocol pre-hook injection.

Injects a ready-to-read markdown summary of failed audit checks so the
dev-ticket verify phase can act without re-running ``audit``. The hook
reuses the ``text`` field each rule already populates (one formatted
line per violation with file:line and code), grouped by rule.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_audit.core.auditor import audit_project
from axm_audit.models import AuditResult, CheckResult

__all__ = ["QualityCheckHook"]

logger = logging.getLogger(__name__)

_DEFAULT_CATEGORIES: list[str] = ["lint", "type"]


def _read_snippet(
    working_dir: Path,
    file: str,
    line: int,
    context_lines: int = 5,
) -> str | None:
    """Extract a source snippet around a violation line.

    Returns formatted snippet with line numbers and ``>`` marker on the
    violation line, or ``None`` when the file/line is invalid.
    """
    if not file or line < 1:
        return None
    try:
        path = Path(working_dir) / file
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    source_lines = text.splitlines()
    if not source_lines or line > len(source_lines):
        return None
    start = max(0, line - 1 - context_lines)
    end = min(len(source_lines), line + context_lines)
    result: list[str] = []
    width = len(str(end))
    for idx in range(start, end):
        lineno = idx + 1
        prefix = (
            f"{lineno}>".rjust(width + 1)
            if lineno == line
            else f"{lineno}: ".rjust(width + 2)
        )
        result.append(f"{prefix} {source_lines[idx]}")
    return "\n".join(result)


def _render_failed_checks(failed_checks: list[CheckResult]) -> str:
    """Render failed checks as a markdown-friendly text block.

    Each rule contributes its headline (``message``) followed by its
    pre-formatted ``text`` (one bullet per underlying violation). Rules
    without ``text`` fall back to ``message`` alone.
    """
    sections: list[str] = []
    for check in failed_checks:
        header = f"### {check.rule_id} — {check.message}"
        body = check.text.strip() if check.text else "(no detail)"
        if check.fix_hint:
            body = f"{body}\nfix: {check.fix_hint}"
        sections.append(f"{header}\n{body}")
    return "\n\n".join(sections)


class QualityCheckHook:
    """Run audit categories and emit a text-only summary of failures."""

    def execute(
        self,
        context: dict[str, Any],
        **params: Any,
    ) -> HookResult:
        """Run audit on a project directory.

        Args:
            context: Hook context with ``working_dir``.
            **params: Optional ``categories`` list.

        Returns:
            HookResult with ``has_violations`` and ``summary`` metadata,
            plus a markdown ``text`` block containing each failed rule
            with its pre-formatted per-violation lines (file:line, code,
            message) ready for direct LLM consumption.
        """
        working_dir = params.get("working_dir") or context.get("working_dir", ".")
        project_path = Path(working_dir)

        if not project_path.is_dir():
            return HookResult.ok(has_violations=False, summary="clean")

        categories: list[str] = params.get("categories", _DEFAULT_CATEGORIES)

        results: list[AuditResult] = []
        for category in categories:
            try:
                result = audit_project(project_path, category=category)
                results.append(result)
            except (OSError, RuntimeError, ValueError):
                logger.warning(
                    "audit_project failed for category=%s", category, exc_info=True
                )

        if not results:
            return HookResult.ok(has_violations=False, summary="clean")

        all_checks: list[CheckResult] = []
        for r in results:
            all_checks.extend(r.checks)

        failed_checks = [c for c in all_checks if not c.passed]

        if not failed_checks:
            return HookResult.ok(has_violations=False, summary="clean")

        text = _render_failed_checks(failed_checks)
        summary = f"{len(failed_checks)} failing check(s)"

        # Note: bypass HookResult.ok() because older installed axm versions
        # swallow `text` into metadata. Build the dataclass directly so the
        # downstream HookRunner sees result.text and injects it verbatim.
        return HookResult(
            success=True,
            text=text,
            metadata={"has_violations": True, "summary": summary},
        )
