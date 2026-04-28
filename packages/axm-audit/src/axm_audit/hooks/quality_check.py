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


def _run_audits(project_path: Path, categories: list[str]) -> list[AuditResult]:
    results: list[AuditResult] = []
    for category in categories:
        try:
            results.append(audit_project(project_path, category=category))
        except (OSError, RuntimeError, ValueError):
            logger.warning(
                "audit_project failed for category=%s", category, exc_info=True
            )
    return results


def _failed_checks_from(results: list[AuditResult]) -> list[CheckResult]:
    return [c for r in results for c in r.checks if not c.passed]


def _clean_result() -> HookResult:
    return HookResult.ok(has_violations=False, summary="clean")


def _violations_result(failed_checks: list[CheckResult]) -> HookResult:
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
            return _clean_result()

        categories: list[str] = params.get("categories", _DEFAULT_CATEGORIES)
        failed_checks = _failed_checks_from(_run_audits(project_path, categories))

        if not failed_checks:
            return _clean_result()

        return _violations_result(failed_checks)
