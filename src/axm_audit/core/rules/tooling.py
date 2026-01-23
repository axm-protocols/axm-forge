"""Tooling rules — CLI tool availability checks."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


@dataclass
class ToolAvailabilityRule(ProjectRule):
    """Check if a required CLI tool is available on PATH."""

    tool_name: str
    critical: bool = True  # If True, severity=ERROR when missing; else WARNING

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"TOOL_{self.tool_name.upper()}"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the tool is available on the system PATH."""
        _ = project_path  # Not used for tool availability checks
        available = shutil.which(self.tool_name) is not None

        if available:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"{self.tool_name} found",
                severity=Severity.INFO,
            )

        severity = Severity.ERROR if self.critical else Severity.WARNING
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.tool_name} not found",
            severity=severity,
            fix_hint=f"Install with: uv tool install {self.tool_name}",
        )
