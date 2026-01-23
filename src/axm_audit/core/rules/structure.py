"""Structure rules — file and directory existence checks."""

from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult


@dataclass
class FileExistsRule(ProjectRule):
    """Rule that checks if a required file exists."""

    file_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"FILE_EXISTS_{self.file_name}"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the file exists in the project."""
        target = project_path / self.file_name
        if target.exists() and target.is_file():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"{self.file_name} exists",
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.file_name} not found",
        )


@dataclass
class DirectoryExistsRule(ProjectRule):
    """Rule that checks if a required directory exists."""

    dir_name: str

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return f"DIR_EXISTS_{self.dir_name}"

    def check(self, project_path: Path) -> CheckResult:
        """Check if the directory exists in the project."""
        target = project_path / self.dir_name
        if target.exists() and target.is_dir():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"{self.dir_name}/ exists",
            )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.dir_name}/ not found",
        )
