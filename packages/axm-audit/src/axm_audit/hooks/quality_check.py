"""Quality-check hook for protocol pre-hook injection."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from axm.hooks.base import HookResult

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult

__all__ = ["QualityCheckHook"]

logger = logging.getLogger(__name__)

_DEFAULT_CATEGORIES: list[str] = ["lint", "type"]


class QualityCheckHook:
    """Run audit categories and report violations as hook metadata."""

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
            HookResult with ``has_violations``, ``violations``, ``summary``.
        """
        working_dir = params.get("working_dir") or context.get("working_dir", ".")
        project_path = Path(working_dir)

        if not project_path.is_dir():
            return HookResult.ok(has_violations=False, violations=[], summary="clean")

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
            return HookResult.ok(has_violations=False, violations=[], summary="clean")

        all_checks = []
        for r in results:
            all_checks.extend(r.checks)

        merged = AuditResult.model_construct(checks=all_checks)
        agent_output = format_agent(merged)

        failed_items = agent_output.get("failed", [])
        violations = [
            {
                "file": item.get("details", {}).get("file", ""),
                "line": item.get("details", {}).get("line", 0),
                "message": item.get("message", ""),
                "code": item.get("rule_id", ""),
                "rule_id": item.get("rule_id", ""),
            }
            for item in failed_items
        ]

        has_violations = len(violations) > 0
        summary = f"{len(violations)} violation(s)" if has_violations else "clean"

        return HookResult.ok(
            has_violations=has_violations,
            violations=violations,
            summary=summary,
        )
