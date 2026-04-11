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


def _expand_violations(
    project_path: Path,
    failed_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand failed audit items into flat violation dicts.

    Items with inner ``errors`` or ``issues`` lists are expanded per entry
    with file/line/snippet. Items without inner lists produce a single
    fallback violation.
    """
    violations: list[dict[str, Any]] = []
    for item in failed_items:
        rule_id = item.get("rule_id", "")
        details = item.get("details") or {}
        inner = details.get("errors", details.get("issues"))
        if inner is not None:
            for entry in inner:
                entry_file = entry.get("file", "")
                entry_line = entry.get("line", 0)
                violations.append(
                    {
                        "file": entry_file,
                        "line": entry_line,
                        "message": entry.get("message", ""),
                        "code": entry.get("code", ""),
                        "rule_id": rule_id,
                        "snippet": _read_snippet(project_path, entry_file, entry_line),
                    }
                )
        else:
            violations.append(
                {
                    "file": "",
                    "line": 0,
                    "message": item.get("message", ""),
                    "code": rule_id,
                    "rule_id": rule_id,
                    "snippet": None,
                }
            )
    return violations


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
            Each violation is expanded from inner error lists when available
            (``errors`` for type checks, ``issues`` for lint checks).
            Checks without inner lists produce a single fallback violation.
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
        violations = _expand_violations(project_path, failed_items)

        has_violations = len(violations) > 0
        summary = f"{len(violations)} violation(s)" if has_violations else "clean"

        return HookResult.ok(
            has_violations=has_violations,
            violations=violations,
            summary=summary,
        )
