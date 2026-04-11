"""Audit quality witness rule.

Runs lint and type checks via ``audit_project`` and returns structured
agent-friendly feedback.  Unlike ``RunCommandRule`` the two categories
execute independently — a lint failure does **not** prevent type checking.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from axm.witnesses import ValidationFeedback, WitnessResult

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_agent
from axm_audit.models.results import AuditResult

logger = logging.getLogger(__name__)

__all__ = ["AuditQualityRule"]

VALID_CATEGORIES = frozenset({"lint", "type", "testing", "complexity", "security"})


@dataclass
class AuditQualityRule:
    """Run audit checks and return structured feedback.

    Attributes:
        categories: Audit categories to run (default: lint + type).
        working_dir: Project root to audit.
        guidance: Optional extra guidance appended on failure.
    """

    categories: list[str] = field(default_factory=lambda: ["lint", "type"])
    working_dir: str = "."
    guidance: str | None = None
    scope: str = "."
    exclude_rules: list[str] = field(default_factory=list)
    extra_dirs: list[str] = field(default_factory=list)

    def _audit_extra_dirs(
        self,
        categories: list[str],
        results: list[AuditResult],
    ) -> None:
        """Run audit categories on each extra directory."""
        for extra_dir in self.extra_dirs:
            extra_path = Path(extra_dir).resolve()
            if not extra_path.is_dir():
                logger.info("Skipping extra_dir: %s does not exist", extra_dir)
                continue
            for category in categories:
                try:
                    result = audit_project(extra_path, category=category)
                    results.append(result)
                except Exception:
                    logger.exception(
                        "audit_project failed for extra_dir=%s category=%s",
                        extra_dir,
                        category,
                    )

    def _run_categories(
        self,
        project_path: Path,
        categories: list[str],
    ) -> list[AuditResult]:
        """Run each audit category independently, collecting results."""
        results: list[AuditResult] = []
        for category in categories:
            try:
                result = audit_project(project_path, category=category)
                results.append(result)
            except Exception:
                logger.exception("audit_project failed for category=%s", category)
        return results

    def _filter_excluded(
        self, failed_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove items whose rule_id matches any exclude prefix."""
        if not self.exclude_rules or not failed_items:
            return failed_items
        return [
            item
            for item in failed_items
            if not any(
                item.get("rule_id", "").startswith(prefix)
                for prefix in self.exclude_rules
            )
        ]

    def _build_failure_result(
        self,
        agent_output: dict[str, Any],
        failed_items: list[dict[str, Any]],
    ) -> WitnessResult:
        """Build a WitnessResult.failure with structured feedback."""
        why_lines = json.dumps(failed_items, indent=2, ensure_ascii=False)
        how = (
            "Fix each violation listed above. Lint errors: fix the code "
            "(do NOT add # noqa). Type errors: fix the types "
            "(do NOT add # type: ignore without verifying)."
        )
        if self.guidance:
            how = f"{how}\n\n{self.guidance}"
        return WitnessResult.failure(
            feedback=ValidationFeedback(
                what=f"Quality gate failed: {len(failed_items)} violation(s)",
                why=why_lines,
                how=how,
            ),
            metadata={"audit": agent_output},
        )

    def validate(self, content: str, **kwargs: Any) -> WitnessResult:
        """Run audit categories and aggregate results.

        Each category runs independently — failures in one do not
        prevent execution of the others.
        """
        working_dir = kwargs.get("working_dir") or self.working_dir
        project_path = Path(working_dir).resolve()

        if not project_path.is_dir():
            return WitnessResult.failure(
                feedback=ValidationFeedback(
                    what="Invalid working directory",
                    why=f"Not a directory: {project_path}",
                    how="Ensure the witness params.working_dir points to "
                    "a valid project root.",
                ),
            )

        # Filter to known categories, skip unknowns
        categories = [c for c in self.categories if c in VALID_CATEGORIES]
        if not categories:
            return WitnessResult.success()

        results = self._run_categories(project_path, categories)
        if not results:
            return WitnessResult.failure(
                feedback=ValidationFeedback(
                    what="All audit categories failed to execute",
                    why="audit_project raised exceptions for every category.",
                    how="Check the project structure and audit configuration.",
                ),
            )

        # Run audits on extra_dirs and aggregate
        self._audit_extra_dirs(categories, results)

        # Aggregate: merge all check results into a single AuditResult
        all_checks = []
        for r in results:
            all_checks.extend(r.checks)

        merged = AuditResult(checks=all_checks)
        agent_output = format_agent(merged)

        # Filter excluded rules before counting failures
        failed_items = self._filter_excluded(agent_output.get("failed", []))
        agent_output["failed"] = failed_items

        if not failed_items:
            return WitnessResult.success(
                metadata={"audit": agent_output},
            )

        return self._build_failure_result(agent_output, failed_items)
